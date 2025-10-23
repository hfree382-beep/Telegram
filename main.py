from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import threading

app = Flask(__name__, static_folder='.')

sessions = {}  # store client by phone

# Create a single persistent event loop in background thread
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

def run_async(coro):
    """Run coroutine safely inside persistent loop"""
    return asyncio.run_coroutine_threadsafe(coro, loop).result()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/send_code', methods=['POST'])
def send_code():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone = data.get("phone")

    if not all([api_id, api_hash, phone]):
        return jsonify({"error": "api_id, api_hash, phone required"}), 400

    async def async_task():
        session = StringSession("")
        client = TelegramClient(session, int(api_id), api_hash)
        await client.connect()
        sent = await client.send_code_request(phone)
        sessions[phone] = {
            "client": client,
            "session": session,
            "phone_code_hash": sent.phone_code_hash,
        }
        return {"message": f"Code sent to {phone}"}

    try:
        result = run_async(async_task())
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/confirm_code', methods=['POST'])
def confirm_code():
    data = request.json
    phone = data.get("phone")
    code = data.get("code")

    if phone not in sessions:
        return jsonify({"error": "Phone session not found. Please send_code first."}), 400

    entry = sessions[phone]
    client = entry["client"]
    phone_code_hash = entry["phone_code_hash"]

    async def async_signin():
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            session_string = client.session.save()
            await client.disconnect()
            del sessions[phone]
            return {"session_string": session_string}
        except Exception as e:
            return {"error": str(e)}

    try:
        result = run_async(async_signin())
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)