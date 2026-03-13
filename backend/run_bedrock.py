import os
from dotenv import load_dotenv
from utils.bedrock_client import get_bedrock_client

load_dotenv()

print("=" * 70)
print("BEDROCK MODEL INVOCATION")
print("=" * 70)

client = get_bedrock_client()

print("\n✓ Bedrock client initialized")
print(f"  Region: {client.region}")
print(f"  Model: {client.model_id}")

print("\n" + "=" * 70)
print("SENDING PROMPT TO BEDROCK")
print("=" * 70)

prompt = "What is synthetic data generation? Explain in 2-3 sentences."
print(f"\nPrompt: {prompt}\n")

response = client.invoke_model(prompt)

print("=" * 70)
print("RESPONSE FROM BEDROCK")
print("=" * 70)
print(response)
print("=" * 70)
