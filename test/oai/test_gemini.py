import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from google.api_core.exceptions import InternalServerError

    from autogen.oai.gemini import GeminiClient

    skip = False
except ImportError:
    GeminiClient = object
    InternalServerError = object
    skip = True


# Fixtures for mock data
@pytest.fixture
def mock_response():
    class MockResponse:
        def __init__(self, text, choices, usage, cost, model):
            self.text = text
            self.choices = choices
            self.usage = usage
            self.cost = cost
            self.model = model

    return MockResponse


@pytest.fixture
def gemini_client():
    return GeminiClient(api_key="fake_api_key")


# Test compute location initialization and configuration
@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
def test_compute_location_initialization():
    with pytest.raises(AssertionError):
        GeminiClient(
            api_key="fake_api_key", location="us-west1"
        )  # Should raise an AssertionError due to specifying API key and compute location


@pytest.fixture
def gemini_google_auth_default_client():
    return GeminiClient()


@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
def test_valid_initialization(gemini_client):
    assert gemini_client.api_key == "fake_api_key", "API Key should be correctly set"


@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
def test_gemini_message_handling(gemini_client):
    messages = [
        {"role": "system", "content": "You are my personal assistant."},
        {"role": "model", "content": "How can I help you?"},
        {"role": "user", "content": "Which planet is the nearest to the sun?"},
        {"role": "user", "content": "Which planet is the farthest from the sun?"},
        {"role": "model", "content": "Mercury is the closest palnet to the sun."},
        {"role": "model", "content": "Neptune is the farthest palnet from the sun."},
        {"role": "user", "content": "How can we determine the mass of a black hole?"},
    ]

    # The datastructure below defines what the structure of the messages
    # should resemble after converting to Gemini format.
    # Messages of similar roles are expected to be merged to a single message,
    # where the contents of the original messages will be included in
    # consecutive parts of the converted Gemini message
    expected_gemini_struct = [
        # system role is converted to user role
        {"role": "user", "parts": ["You are my personal assistant."]},
        {"role": "model", "parts": ["How can I help you?"]},
        {
            "role": "user",
            "parts": ["Which planet is the nearest to the sun?", "Which planet is the farthest from the sun?"],
        },
        {
            "role": "model",
            "parts": ["Mercury is the closest palnet to the sun.", "Neptune is the farthest palnet from the sun."],
        },
        {"role": "user", "parts": ["How can we determine the mass of a black hole?"]},
    ]

    converted_messages = gemini_client._oai_messages_to_gemini_messages(messages)

    assert len(converted_messages) == len(expected_gemini_struct), "The number of messages is not as expected"

    for i, expected_msg in enumerate(expected_gemini_struct):
        assert expected_msg["role"] == converted_messages[i].role, "Incorrect mapped message role"
        for j, part in enumerate(expected_msg["parts"]):
            assert converted_messages[i].parts[j].text == part, "Incorrect mapped message text"


# Test error handling
@patch("autogen.oai.gemini.genai")
@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
def test_internal_server_error_retry(mock_genai, gemini_client):
    mock_genai.GenerativeModel.side_effect = [InternalServerError("Test Error"), None]  # First call fails
    # Mock successful response
    mock_chat = MagicMock()
    mock_chat.send_message.return_value = "Successful response"
    mock_genai.GenerativeModel.return_value.start_chat.return_value = mock_chat

    with patch.object(gemini_client, "create", return_value="Retried Successfully"):
        response = gemini_client.create({"model": "gemini-pro", "messages": [{"content": "Hello"}]})
        assert response == "Retried Successfully", "Should retry on InternalServerError"


# Test cost calculation
@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
def test_cost_calculation(gemini_client, mock_response):
    response = mock_response(
        text="Example response",
        choices=[{"message": "Test message 1"}],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost=0.01,
        model="gemini-pro",
    )
    assert gemini_client.cost(response) > 0, "Cost should be correctly calculated as zero"


@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
@patch("autogen.oai.gemini.Content")
@patch("autogen.oai.gemini.genai.GenerativeModel")
@patch("autogen.oai.gemini.genai.configure")
def test_create_response(mock_configure, mock_generative_model, mock_content, gemini_client):
    # Mock the genai model configuration and creation process
    mock_chat = MagicMock()
    mock_model = MagicMock()
    mock_configure.return_value = None
    mock_generative_model.return_value = mock_model
    mock_model.start_chat.return_value = mock_chat

    # Set up a mock for the chat history item access and the text attribute return
    mock_history_part = MagicMock()
    mock_history_part.text = "Example response"
    mock_history_part.function_call = None
    mock_chat.history.__getitem__.return_value.parts.__iter__.return_value = iter([mock_history_part])

    # Setup the mock to return a mocked chat response
    mock_chat.send_message.return_value = MagicMock(history=[MagicMock(parts=[MagicMock(text="Example response")])])

    # Call the create method
    response = gemini_client.create(
        {"model": "gemini-pro", "messages": [{"content": "Hello", "role": "user"}], "stream": False}
    )

    # Assertions to check if response is structured as expected
    assert response.choices[0].message.content == "Example response", "Response content should match expected output"


@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
@patch("autogen.oai.gemini.Part")
@patch("autogen.oai.gemini.Content")
@patch("autogen.oai.gemini.genai.GenerativeModel")
@patch("autogen.oai.gemini.genai.configure")
def test_create_function_call_response(mock_configure, mock_generative_model, mock_content, mock_part, gemini_client):
    # Mock the genai model configuration and creation process
    mock_chat = MagicMock()
    mock_model = MagicMock()
    mock_configure.return_value = None
    mock_generative_model.return_value = mock_model
    mock_model.start_chat.return_value = mock_chat

    mock_part.to_dict.return_value = {
        "function_call": {"name": "function_name", "args": {"arg1": "value1", "arg2": "value2"}}
    }

    # Set up a mock for the chat history item access and the text attribute return
    mock_history_part = MagicMock()
    mock_history_part.text = None
    mock_history_part.function_call.name = "function_name"
    mock_history_part.function_call.args = {"arg1": "value1", "arg2": "value2"}
    mock_chat.history.__getitem__.return_value.parts.__iter__.return_value = iter([mock_history_part])

    # Setup the mock to return a mocked chat response
    mock_chat.send_message.return_value = MagicMock(
        history=[
            MagicMock(
                parts=[
                    MagicMock(
                        function_call=MagicMock(name="function_name", arguments='{"arg1": "value1", "arg2": "value2"}')
                    )
                ]
            )
        ]
    )

    # Call the create method
    response = gemini_client.create(
        {"model": "gemini-pro", "messages": [{"content": "Hello", "role": "user"}], "stream": False}
    )

    # Assertions to check if response is structured as expected
    assert (
        response.choices[0].message.tool_calls[0].function.name == "function_name"
        and json.loads(response.choices[0].message.tool_calls[0].function.arguments)["arg1"] == "value1"
    ), "Response content should match expected output"


@pytest.mark.skipif(skip, reason="Google GenAI dependency is not installed")
@patch("autogen.oai.gemini.genai.GenerativeModel")
@patch("autogen.oai.gemini.genai.configure")
def test_create_vision_model_response(mock_configure, mock_generative_model, gemini_client):
    # Mock the genai model configuration and creation process
    mock_model = MagicMock()
    mock_configure.return_value = None
    mock_generative_model.return_value = mock_model

    # Set up a mock to simulate the vision model behavior
    mock_vision_response = MagicMock()
    mock_vision_part = MagicMock(text="Vision model output", function_call=None)

    # Setting up the chain of return values for vision model response
    mock_vision_response._result.candidates.__getitem__.return_value.content.parts.__iter__.return_value = iter(
        [mock_vision_part]
    )
    mock_model.generate_content.return_value = mock_vision_response

    # Call the create method with vision model parameters
    response = gemini_client.create(
        {
            "model": "gemini-pro-vision",  # Vision model name
            "messages": [
                {
                    "content": [
                        {"type": "text", "text": "Let's play a game."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg=="
                            },
                        },
                    ],
                    "role": "user",
                }
            ],  # Assuming a simple content input for vision
            "stream": False,
        }
    )

    # Assertions to check if response is structured as expected
    assert (
        response.choices[0].message.content == "Vision model output"
    ), "Response content should match expected output from vision model"
