from astra_audio.soundscape_planner import plan_soundscape, SCHEMA


def test_world_locations_and_foley_are_not_train_specific():
    script='''दृश्य 1: सुनसान जंगल का रास्ता
वह अकेला सूखे पत्तों पर धीरे-धीरे चल रहा था।
अचानक वह झाड़ियों से निकला और एक सूखी टहनी टूट गई।
दृश्य 2: श्मशान का रास्ता
वह खाली सड़क पर अकेला आगे बढ़ा।'''
    result=plan_soundscape(script)
    assert result['schema']==SCHEMA and result['scene_count']==2
    forest=result['scenes'][0]
    assert forest['primary_environment'] in {'forest','jungle'}
    events={x['event'] for x in forest['action_foley']}
    assert {'walk_leaves','brush_through','branch_snap'} <= events
    cemetery=result['scenes'][1]
    assert cemetery['primary_environment']=='cemetery'
    assert cemetery['environment_layers']


def test_unknown_world_gets_conservative_fallback():
    result=plan_soundscape('एक अज्ञात ग्रह पर यात्री उतरता है।')
    scene=result['scenes'][0]
    assert scene['primary_environment']=='unspecified_world_location'
    assert scene['review_required'] is True
    assert result['asset_generation_performed'] is False


def test_no_automatic_horror_noise_from_cemetery_alone():
    result=plan_soundscape('दृश्य: श्मशान का रास्ता। वह चुपचाप चल रहा था।')
    scene=result['scenes'][0]
    assert scene['primary_environment']=='cemetery'
    assert 'automatic_ghost_sounds' in scene['environment_alternatives'][0]['profile'].get('avoid',[])
