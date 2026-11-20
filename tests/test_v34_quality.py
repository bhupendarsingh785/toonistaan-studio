import numpy as np, soundfile as sf
from pathlib import Path
from tools.script_pipeline import parse_script_line, prepare_script
from tools.audio_qa import inspect_wav

def test_speaker_and_emotion_prefix_orders():
    assert parse_script_line('[dukh] दादी: बेटा आ जा।') == {'speaker':'दादी','emotion':'dukh','text':'बेटा आ जा।'}
    assert parse_script_line('दादी [gussa]: चुप रहो!') == {'speaker':'दादी','emotion':'gussa','text':'चुप रहो!'}

def test_hindi_combining_sequence_not_split_apart():
    text='क्‍ष' * 30
    chunks=prepare_script(text,max_chars=40)
    assert ''.join(x['text'] for x in chunks)==text

def test_audio_qa_passes_clean_wav(tmp_path):
    p=tmp_path/'clean.wav'; sf.write(p,np.sin(np.arange(24000)*2*np.pi*220/24000).astype('float32')*.15,24000)
    r=inspect_wav(p)
    assert r['pass'] and r['duration_sec']==1.0 and not r['warnings']

def test_audio_qa_rejects_silence(tmp_path):
    p=tmp_path/'silent.wav'; sf.write(p,np.zeros(24000,dtype='float32'),24000)
    r=inspect_wav(p)
    assert not r['pass'] and 'mostly_silence' in r['warnings']

def test_text_scores_detect_hindi_text_errors():
    from tools.evaluate_generation import text_scores
    exact = text_scores('नमस्ते दुनिया', 'नमस्ते दुनिया')
    changed = text_scores('नमस्ते दुनिया', 'नमस्ते भारत')
    assert exact['wer'] == 0 and exact['cer'] == 0
    assert changed['wer'] > 0 and changed['cer'] > 0

def test_preflight_does_not_claim_inference_verified():
    from tools.preflight import report
    r=report()
    assert r['backends']['indicf5']['inference_verified'] is False
    assert r['backends']['xtts']['inference_verified'] is False
