import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from characterize import simulate

def evidence():return json.loads((ROOT/'reports/characterization.json').read_text())

def test_unmodified_pdk_models():
    p=json.loads((ROOT/'models/provenance.json').read_text())
    assert len(p['commit'])==40
    for name,digest in p['files_sha256'].items():assert hashlib.sha256((ROOT/'models'/name).read_bytes()).hexdigest()==digest

def test_full_operating_envelope():
    j=evidence();rows=j['pvt_conditions'];assert len(rows)==135
    assert len({(r['corner'],r['vdd_v'],r['temp_c'],r['cl_f']) for r in rows})==135
    assert all(r['dc_gain_db']>=60 and r['unity_hz']>=5e6 and r['phase_margin_deg']>=50 for r in rows)

def test_compensation_tradeoff():
    rows=evidence()['compensation_sweep'];r=[x for x in rows if x['rz_ohm']==2000]
    r.sort(key=lambda x:x['cc_f'])
    assert all(a['unity_hz']>b['unity_hz'] for a,b in zip(r,r[1:]))
    assert all(a['phase_margin_deg']<b['phase_margin_deg'] for a,b in zip(r,r[1:]))

def test_negative_control_rejects_undercompensation():
    r=simulate('negative-control',cc=.1e-12,rz=.1)
    assert r['phase_margin_deg']<50,'unstable/poorly damped candidate must be rejected'

def test_dc_offset_and_power():
    j=evidence()['nominal'];assert abs(j['input_offset_v'])<.001
    assert 100e-6<j['power_w']<500e-6

def test_transient_settles_both_directions():
    r=evidence()['transient'];assert 0<r['positive_settling_1pct_s']<100e-9
    assert 0<r['negative_settling_1pct_s']<100e-9
    assert r['positive_peak_slope_v_per_s']>0>r['negative_peak_slope_v_per_s']

def test_noise_band_and_units():
    n=evidence()['noise'];assert n['noise_band_hz']==[10,1e7]
    assert 0<n['input_noise_rms_v']<.001
    assert 0<n['noise_1khz_v_sqrt_hz']<1e-5

def test_report_matches_current_circuit():
    assert evidence()['circuit_sha256']==hashlib.sha256((ROOT/'circuits/ota.spice').read_bytes()).hexdigest()
