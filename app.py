import streamlit as st
import websockets
import asyncio
import base64
import json
import pyaudio
import os
from pathlib import Path
import requests
import pandas as pd

hide_st_style = """
            <style>
            
            footer {visibility: hidden;}
            
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Session state
if 'text' not in st.session_state:
	st.session_state['text'] = 'Listening...'
	st.session_state['run'] = False
	st.session_state['transcriptions'] = []
	# st.session_state['selected_message'] = None

# Audio parameters 
st.sidebar.header('Audio Parameters')

FRAMES_PER_BUFFER = int(st.sidebar.text_input('Frames per buffer', 16384))
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = int(st.sidebar.text_input('Rate', 16000))
# RATE = st.sidebar.number_input('Sample rate', min_value=1, max_value=96000, value=16000)
# FRAMES_PER_BUFFER = st.sidebar.slider('Frames per buffer', min_value=64, max_value=8192, value=1024, step=64)

p = pyaudio.PyAudio()

# Open an audio stream with above parameter settings
stream = p.open(
   format=FORMAT,
   channels=CHANNELS,
   rate=RATE,
   input=True,
   frames_per_buffer=FRAMES_PER_BUFFER
)

# Start/stop audio transmission
def start_listening():
	st.session_state['run'] = True

def download_transcription():
	read_txt = open('transcription.txt', 'r')
	st.download_button(
		label="Download transcription",
		data=read_txt,
		file_name='transcription_output.txt',
		mime='text/plain')

def stop_listening():
	st.session_state['run'] = False
	
def translate_text(text):
    url = "https://api-b2b.backenster.com/b1/api/v3/translate"

    payload = {
        "translateMode": "html",
        "platform": "api",
        "from":"en_GB",
        "to": "rw_RW",
        "text": text
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "a_0kbBzrwgPxQR9RQetqPb4PGt8mzJFJwK9rytriJ884xxhNor0vdYBOSYREHU4YeSUAJLhxkJuo3GKbb6"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        response_json = response.json()
        print("Response JSON:", response_json)  # Print the response JSON
        translated_text = response_json["result"]
    
	
        return translated_text
    else:
        print(f"Translation Error: {response.status_code}, {response.text}")
        return text


# Web user interface
st.title('🎙️ Real-Time Transcription App')


with st.expander('About this App'):
	st.markdown('''
	This Streamlit that performs real-time transcription from English Speech to Kinyarwanda Text.
	
	Libraries used:
	- `streamlit` - web framework
	- `pyaudio` - a Python library providing bindings to [PortAudio](http://www.portaudio.com/) (cross-platform audio processing library)
	- `asyncio` - allows concurrent input/output processing
	- `base64` - encode/decode audio data
	- `json` - allows reading of audio output in JSON format
	''')



with st.sidebar:
    st.header("Transcription")
    if st.button("Show Transcription"):
        st.session_state["show_transcription"] = not st.session_state.get("show_transcription", False)

if st.session_state.get("show_transcription", False):
    st.header("Transcriptions")
    
    # Combine all Kinyarwanda transcriptions into one paragraph
    kinyarwanda_paragraph = ' '.join([row['Kinyarwanda'] for row in st.session_state['transcriptions']])
    
    # Display the combined Kinyarwanda paragraph with a slightly larger font size
    st.markdown(f'<p style="font-size: 1.25em">{kinyarwanda_paragraph}</p>', unsafe_allow_html=True)
    
    transcriptions_df = pd.DataFrame(st.session_state['transcriptions'], columns=["English", "Kinyarwanda"])
    st.write(transcriptions_df.style.set_table_styles([
        {'selector': 'th', 'props': [('background', '#f2f2f2'), ('color', 'black'), ('font-weight', 'bold'), ('text-align', 'center')]},
        {'selector': 'td', 'props': [('background', '#f9f9f9'), ('color', 'black'), ('text-align', 'center')]},
        {'selector': 'tr:nth-of-type(odd)', 'props': [('background', '#ffffff')]},
        {'selector': 'tr:nth-of-type(even)', 'props': [('background', '#f9f9f9')]},
    ]))



col1, col2 = st.columns(2)

col1.button('Start', on_click=start_listening)
col2.button('Stop', on_click=stop_listening)

# Send audio (Input) / Receive transcription (Output)
async def send_receive():
	URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"

	print(f'Connecting websocket to url ${URL}')

	async with websockets.connect(
		URL,
		extra_headers=(("Authorization", st.secrets['api_key']),),
		ping_interval=5,
		ping_timeout=20
	) as _ws:

		r = await asyncio.sleep(0.1)
		print("Receiving messages ...")

		session_begins = await _ws.recv()
		print(session_begins)
		print("Sending messages ...")

        
		async def send():
			while st.session_state['run']:
				try:
					data = stream.read(FRAMES_PER_BUFFER)
					data = base64.b64encode(data).decode("utf-8")
					json_data = json.dumps({"audio_data":str(data)})
					r = await _ws.send(json_data)

				except websockets.exceptions.ConnectionClosedError as e:
					print(e)
					if e.code != 4008:
						break
						

				except Exception as e:
					print(f"Unexpected error: {type(e).__name__}: {e}")
					
				r = await asyncio.sleep(0.01)
		# 


		async def receive():
			while st.session_state['run']:
				try:
					result_str = await _ws.recv()
					result = json.loads(result_str)['text']

					if json.loads(result_str)['message_type']=='FinalTranscript':
						print(result)
						translated_result = translate_text(result)
						st.session_state['text'] = translated_result
						st.session_state['transcriptions'].append({"English": result, "Kinyarwanda": st.session_state['text']})

					
						# st.session_state['text'] = result
						if st.session_state['text'] != 'Listening...':
							st.write(st.session_state['text'])


						transcription_txt = open('transcription.txt', 'a')
						transcription_txt.write(st.session_state['text'])
						transcription_txt.write(' ')
						transcription_txt.close()


				except websockets.exceptions.ConnectionClosedError as e:
					print(e)
					assert e.code == 4008
					break

				except Exception as e:
					print(e)
					assert False, "Not a websocket 4008 error"
			
		send_result, receive_result = await asyncio.gather(send(), receive())


asyncio.run(send_receive())

if Path('transcription.txt').is_file():
	st.markdown('### Download')
	download_transcription()
	os.remove('transcription.txt')

