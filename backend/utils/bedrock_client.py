import os
from typing import Optional
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

class BedrockClient:
    def __init__(self, region: str = "us-east-1", model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"):
        self.region = region
        self.model_id = model_id
        
        # Get bearer token from environment
        bearer_token = os.getenv("AWS_BEARER_TOKEN")
        
        if not bearer_token:
            raise ValueError("AWS_BEARER_TOKEN not configured in environment")
        
        # Initialize ChatBedrockConverse with bearer token
        self.llm = ChatBedrockConverse(
            model=model_id,
            region_name=region,
            api_key=bearer_token,
            temperature=0.7,
            max_tokens=4096
        )
    
    def invoke_model(self, prompt: str, max_tokens: int = 1024) -> str:
        """Invoke Bedrock model with the given prompt"""
        try:
            response = self.llm.invoke([
                HumanMessage(content=prompt)
            ])
            return response.content
        except Exception as e:
            raise Exception(f"Failed to invoke Bedrock model: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Bedrock service is available"""
        try:
            response = self.llm.invoke([
                HumanMessage(content="test")
            ])
            return bool(response.content)
        except Exception:
            return False


def get_bedrock_client() -> Optional[BedrockClient]:
    """Factory function to create Bedrock client from environment variables"""
    region = os.getenv("AWS_BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("AWS_BEDROCK_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0")
    
    return BedrockClient(region, model_id)
