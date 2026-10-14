"""Radio imaging: editable prompts, speech, music and sound effects."""
import os

import streamlit as st

from audio_catalog import models_for
from audio_providers import AudioRequest, ProviderError, enhance_prompt, generate

st.set_page_config(page_icon='🎙️', layout='wide', page_title='Radio Imaging Audio Generator')
st.title('Radio Imaging Audio Generator')
st.write('Create voiceovers, music beds and sound effects for your radio imaging projects.')

with st.expander('📘 How to use this app'):
    st.markdown('''1. Choose speech, music or sound effects, then a provider and model.
2. Enter your own provider API key. Provider billing and access restrictions apply.
3. Write the exact spoken script or describe the music/sound you want.
4. Optionally enhance your idea with OpenAI, then review and edit the result.
5. Generate, listen and download. Generation runs only when you click its button.''')
    st.caption('Speech is AI-generated. Disclose this to listeners. Use only voices you have permission to use.')

with st.sidebar:
    task = st.selectbox('Audio type', ('Music', 'Speech', 'Sound effects'))
    providers = list(dict.fromkeys(m.provider for m in models_for(task)))
    provider = st.selectbox('Audio provider', providers, key=f'provider_{task}')
    choices = models_for(task, provider)
    model_id = st.selectbox('Audio model', [m.model for m in choices], key=f'model_{task}_{provider}')
    spec = next(m for m in choices if m.model == model_id)
    if spec.note:
        st.caption(spec.note)
    audio_key = ''
    if provider != 'Local MusicGen':
        audio_key = st.text_input(f'{provider} API key', type='password', key=f'key_{provider}', max_chars=512)
    else:
        st.info('Local inference needs the optional local dependencies and ENABLE_LOCAL_MUSICGEN=1.')
    st.caption('Keys stay in this browser session and are sent only to their provider. Prompts and audio are not saved by this app.')
    st.divider()
    st.markdown('**Optional prompt enhancement**')
    if provider == 'OpenAI':
        prompt_key = audio_key
    else:
        prompt_key = st.text_input('OpenAI API key for prompt writing', type='password',
                                   key='prompt_openai_key', max_chars=512)
    prompt_model = st.text_input('OpenAI prompt model', value=os.environ.get('OPENAI_PROMPT_MODEL', 'gpt-5.4-mini'),
                                 max_chars=100)
    st.caption('Use any text model compatible with the OpenAI Responses API.')
    st.markdown('Made with ❤️ by [Bilsimaging](https://bilsimaging.com)')
    st.markdown('[Video tutorials](https://www.youtube.com/playlist?list=PLwEbW4bdYBSDe6qAJRFiWGyHSW-JR-B0_)')

content_key = f'content_{task}'
idea = st.text_area('Your draft idea', max_chars=4000, key=f'idea_{task}',
                    help='Optional: describe your idea, then enhance it or enter the final content below.')
if st.button('📄 Generate Prompt'):
    try:
        with st.spinner('Writing your prompt…'):
            st.session_state[content_key] = enhance_prompt(idea, task, prompt_key, prompt_model)
    except ProviderError as error:
        st.error(str(error))
    except Exception:
        st.error('Prompt generation failed. Please check your settings and try again.')

label = 'Script to speak verbatim' if task == 'Speech' else 'Reviewed audio description'
text = st.text_area(label, key=content_key, max_chars=spec.max_chars,
                    help='Edit this before generating. You can enter text directly without prompt enhancement.')
st.download_button('Download Prompt', text, file_name='generated_prompt.txt', mime='text/plain')
voice = style = ''
seconds = 10.0
instrumental = False
if task == 'Speech':
    st.info('This voice is AI-generated. Speech models read the script; music and effects are generated separately.')
    if spec.voices:
        voice = st.selectbox('Voice', spec.voices, key=f'voice_{provider}_{model_id}')
    else:
        voice = st.text_input('Voice ID', key=f'voice_{provider}', max_chars=100)
    if spec.style:
        style = st.text_area('Delivery instructions (optional)', max_chars=1000,
                             key=f'style_{provider}', help='For example: warm, energetic station announcer.')
if spec.max_seconds:
    seconds = st.slider('Duration (seconds)', float(spec.min_seconds), float(spec.max_seconds),
                        min(10.0, float(spec.max_seconds)), step=0.5,
                        key=f'duration_{provider}_{task}_{model_id}')
if spec.instrumental:
    instrumental = st.checkbox('Instrumental only', value=True)

st.caption('Cloud generation sends your reviewed content to the selected provider and may incur charges. No automatic retries.')
if st.button('▶ Generate Audio', type='primary'):
    try:
        with st.spinner('Generating audio…'):
            result = generate(AudioRequest(spec, text, audio_key, voice, style, seconds, instrumental))
        st.session_state['audio_result'] = result
        st.session_state['audio_description'] = text
        st.session_state['audio_source'] = f'{provider} / {model_id}'
    except ProviderError as error:
        st.error(str(error))
    except Exception:
        st.error('Audio generation failed. Please check your settings and try again.')

if 'audio_result' in st.session_state:
    result = st.session_state['audio_result']
    st.subheader('Last generated audio')
    st.caption(st.session_state['audio_source'])
    st.text(st.session_state['audio_description'])
    st.audio(result.data, format=result.mime)
    st.download_button('Download Audio', result.data,
                       file_name=f'Bilsimaging_radio_imaging_output.{result.extension}', mime=result.mime)

if st.button('Clear session content and audio'):
    for key in list(st.session_state):
        if key.startswith(('audio_', 'content_', 'idea_', 'style_')):
            del st.session_state[key]
    st.rerun()

st.divider()
st.markdown('© Created through Radio Imaging Audio Generator by [Bilsimaging](https://bilsimaging.com).')
st.markdown('For radio producers and music creators. [Try our GPT](https://chat.openai.com/g/g-65x53n87E-radio-imaging-musicgen-ai).')
st.markdown('Support continued development: [Buy me a Coffee](https://ko-fi.com/bilsimaging).')
