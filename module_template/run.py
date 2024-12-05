#!/usr/bin/env python
import os
import json
import subprocess
from dotenv import load_dotenv
from naptha_sdk.schemas import AgentRunInput, OrchestratorRunInput, EnvironmentRunInput
from naptha_sdk.utils import get_logger
from module_template.schemas import InputSchema
from typing import Union

load_dotenv()

logger = get_logger(__name__)

# Path to the LLM configs
LLM_CONFIG_PATH = "module_template/configs/llm_configs.json"

# Load LLM configs from file
def load_llm_configs(config_path=LLM_CONFIG_PATH):
    try:
        with open(config_path, 'r') as f:
            configs = json.load(f)
        return {config['config_name']: config for config in configs}
    except FileNotFoundError:
        logger.error(f"LLM config file not found at {config_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM config file at {config_path}")
        return {}

# Basic module definition
class BasicModule:
    def __init__(self, module_run: Union[AgentRunInput, OrchestratorRunInput, EnvironmentRunInput], llm_config_name: str):
        self.module_run = module_run

        # Load LLM configs
        self.llm_configs = load_llm_configs()
        if llm_config_name not in self.llm_configs:
            raise ValueError(f"LLM config '{llm_config_name}' not found in {LLM_CONFIG_PATH}")
        self.llm_config = self.llm_configs[llm_config_name]

    def func(self, input_data):
        logger.info("Running module function")

        # Extract necessary parameters from the loaded LLM config
        model = self.llm_config["model"]
        temperature = self.llm_config["temperature"]
        max_tokens = self.llm_config["max_tokens"]
        api_base = self.llm_config["api_base"]
        client = self.llm_config["client"]

        # Check if the client is 'openai' or 'ollama'
        if client == "openai":
            api_key = os.getenv("OPENAI_API_KEY")

            headers = [
                "Content-Type: application/json",
                f"Authorization: Bearer {api_key}"
            ]
            data = {
                "model": model,
                "messages": [{"role": "user", "content": "What are you?"}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            data_json = json.dumps(data)
            curl_command = [
                "curl",
                "-X", "POST",
                f"{api_base}/chat/completions",
                "-H", headers[0],
                "-H", headers[1],
                "-d", data_json,
            ]

        elif client == "ollama":
            headers = ["Content-Type: application/json"]
            data = {
                "model": model,
                "messages": [{"role": "user", "content": "What are you?"}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            data_json = json.dumps(data)
            curl_command = [
                "curl",
                "-X", "POST",
                f"{api_base}/api/generate",
                "-H", headers[0],
                "-d", data_json,
            ]

        else:
            logger.error(f"Client '{client}' not supported.")
            return f"Client '{client}' not supported."

        
        try:
            result = subprocess.run(
                curl_command,
                capture_output=True,
                text=True,
                check=True,
            )
            response = json.loads(result.stdout)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "No content")
            return content.strip()
        except subprocess.CalledProcessError as e:
            return "Failed to get response from API."
        except json.JSONDecodeError:
            return "Invalid API response format."
        except Exception as e:
            logger.error(f"Error: {e}")
            return "An error occurred."

# Default entrypoint when the module is executed
def run(module_run: Union[AgentRunInput, OrchestratorRunInput, EnvironmentRunInput], llm_config_name: str):
    basic_module = BasicModule(module_run, llm_config_name)
    method = getattr(basic_module, module_run.inputs.func_name, None)
    return method(module_run.inputs.func_input_data)

if __name__ == "__main__":
    # For testing locally
    from naptha_sdk.client.naptha import Naptha
    from naptha_sdk.configs import load_agent_deployments

    # User can select 'model_1' or 'model_2'
    llm_config_name = "model_2"

    naptha = Naptha()
    input_params = InputSchema(func_name="func", func_input_data="gm...")

    # Load agent deployments
    agent_deployments = load_agent_deployments(
        "module_template/configs/agent_deployments.json",
        load_persona_data=False,
        load_persona_schema=False,
    )

    agent_run = AgentRunInput(
        inputs=input_params,
        agent_deployment=agent_deployments[0],
        consumer_id=naptha.user.id,
    )

    response = run(agent_run, llm_config_name)
    print("Response:\n", response)
