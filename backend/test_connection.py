"""Run with: uv run python -m backend.test_connection"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a terminal prompt to Gemma.")
    parser.add_argument("prompt", nargs="?", help="Prompt text; asks interactively if omitted.")
    args = parser.parse_args()
    try:
        prompt = (args.prompt if args.prompt is not None else input("Your prompt: ")).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 1
    if not prompt:
        print("Please enter a non-empty prompt.")
        return 1

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("Missing GEMINI_API_KEY. Add it to the project's .env file.")
        return 1

    try:
        with genai.Client(
            api_key=key, http_options=types.HttpOptions(timeout=30000),
        ) as client:
            model = os.getenv("GEMINI_MODEL", "").strip()
            if not model:
                # Discover a supported Gemma model rather than assume a model ID.
                models = [
                    item.name for item in client.models.list()
                    if item.name and "gemma" in item.name.lower()
                    and "generateContent" in (item.supported_actions or [])
                ]
                if not models:
                    print("Authentication worked, but no Gemma text models were listed.")
                    print("Set GEMINI_MODEL in .env to an available model ID and retry.")
                    return 1
                model = next((name for name in models if "gemma-4" in name), models[0])

            print(f"Testing model: {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=2048),
            )
            if not response.text or not response.text.strip():
                print("The API responded, but returned no text. Try another model.")
                return 1
            print("\nGemma response:\n")
            print(response.text.replace(key, "[REDACTED]"))
            return 0
    except errors.APIError as exc:
        # Avoid printing raw errors or request URLs that might contain credentials.
        print(f"Google API request failed (HTTP {exc.code}).")
        print({
            400: "Check the API key and model configuration.",
            401: "The API key could not authenticate.",
            403: "Check the key's permissions and API access in Google AI Studio.",
            404: "That model is unavailable. Check GEMINI_MODEL.",
            429: "Quota or rate limit reached. Check usage in Google AI Studio.",
        }.get(exc.code, "The service may be temporarily unavailable. Try again later."))
        return 1
    except Exception as exc:
        print(f"Connection test failed ({type(exc).__name__}).")
        print("Check your internet connection and retry. No credentials were printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
