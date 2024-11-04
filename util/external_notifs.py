"""
Send messages to external devices.
"""

import requests
import os

### TELEGRAM
ENV_TELE_BOT_TOKEN = "KRATOS_TELE_BOT_TOKEN"
ENV_TELE_CHAT_ID = "KRATOS_TELE_CHAT_ID"

def telegram_get_chat_id(token: str) -> str|None:
    """
    Gets the chat ID to be exported as an environment variable with the name specified under ENV_TELE_CHAT_ID for telegram_notify to work.
    """
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    resp = requests.get(url)

    if resp.status_code != 200:
        print("(!) Failed to get chat ID.")
        return None
    
    body = resp.json()
    if not body['ok']:
        print("(!) Failed to get chat ID.")
        return None
    
    result = body['result']
    if len(result) == 0:
        print("(!) Failed to get chat ID.")
        return None

    chat_id = result[0]['message']['chat']['id']
    print(f"(!) Got chat ID: {chat_id}")
    return chat_id


def telegram_notify(msg: str ="Hello from Kratos!") -> bool:
    """
    Requires the following setup:
    1. Make a new Telegram bot using BotFather, then start a conversation with this bot.
    2. Export the token provided as an environment variable with the name specified under ENV_TELE_BOT_TOKEN.
    3. Obtain the chat ID using the telegram_get_chat_id function above, and export it as an environment variable with the name specified under ENV_TELE_CHAT_ID.

    The "msg" provided will be sent directly to this chat.
    Returns True if the message was successfully sent, False otherwise.
    """
    # define error message format.
    def error_msg(error_msg: str) -> None:
        print(f"(!) Cannot send Telegram notification: {error_msg}")

    # check for bot token.
    bot_token = os.getenv(ENV_TELE_BOT_TOKEN)
    if bot_token is None:
        error_msg(f"{ENV_TELE_BOT_TOKEN} not set.")
        return False
    
    # check for chat ID.
    chat_id = os.getenv(ENV_TELE_CHAT_ID)
    if chat_id is None:
        error_msg(f"{ENV_TELE_CHAT_ID} not set.")
        return False
    
    # send message.
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={msg}"
    resp = requests.get(url)
    
    # check for success.
    success = resp.status_code == 200
    print(f"(!) {'Sent' if success else 'Could not send'} message: {msg}")

    return success
### -------