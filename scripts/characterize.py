#!/usr/bin/env python3
"""Characterize the actual SKY130 transistor netlist with batch ngspice."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'
REPORTS=ROOT/'reports'

def simulate(name,corner='tt',vdd=1.8,temp=27,cl=2e-12,cc=2e-12,rz=2000,mode='ac',step=.1,cm=.9):
    folder=BUILD/name;folder.mkdir(parents=True,exist_ok=True)
    vin=f'VIN inp 0 dc {cm} ac 1' if mode!='tran' else f'VIN inp 0 PWL(0 {cm} 1u {cm} 1.001u {cm+step} 3u {cm+step} 3.001u {cm-step} 5u {cm-step} 5.001u {cm})'
    feedback='Lfb out inn 1G\nCac inn 0 1' if mode in ('ac','noise') else 'Vfb out inn 0'
    analysis=''
    if mode=='ac': analysis=f'ac dec 80 1 1G\nlet hre=real(v(out))\nlet him=imag(v(out))\nwrdata {folder}/ac.dat hre him'
    elif mode=='noise':analysis=f'noise v(out) VIN dec 60 10 10Meg\nsetplot noise1\nwrdata {folder}/noise.dat inoise_spectrum onoise_spectrum'
    elif mode=='tran':analysis=f'tran 0.5n 7u\nwrdata {folder}/tran.dat v(inp) v(out)'
    deck=f'''Miller OTA: {name}
.option scale=1e-6
.temp {temp}
.include "{ROOT}/models/{corner}.spice"
.include "{ROOT}/circuits/ota.spice"
VDD vdd 0 {vdd}
{vin}
{feedback}
Xamp inp inn out vdd 0 ota cc={cc} rz={rz}
CL out 0 {cl}
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
let supply=-i(vdd)
wrdata {folder}/op.dat v(out) v(xamp.mid) v(xamp.tail) supply
{analysis}
quit
.endc
.end
'''
    p=folder/'test.cir';p.write_text(deck)
    proc=subprocess.run(['ngspice','-b',str(p)],cwd=ROOT,text=True,capture_output=True,timeout=30)
    (folder/'ngspice.log').write_text(proc.stdout+proc.stderr)
    if proc.returncode or 'Error' in proc.stderr:raise RuntimeError(f'failed {name}: {proc.stderr[-1500:]}')
    op=np.loadtxt(folder/'op.dat',skiprows=1,ndmin=2)[0]
    result={'name':name,'corner':corner,'vdd_v':vdd,'temp_c':temp,'cl_f':cl,'cc_f':cc,'rz_ohm':rz,
            'output_dc_v':float(op[1]),'input_offset_v':float(cm-op[1]),'power_w':float(vdd*op[4]),'mode':mode}
    if mode=='ac':
        a=np.loadtxt(folder/'ac.dat',skiprows=1);f=a[:,0];h=a[:,1]+1j*a[:,2]
        gain=20*np.log10(abs(h));phase=np.rad2deg(np.unwrap(np.angle(h)))
        crossing=np.flatnonzero((gain[:-1]>=0)&(gain[1:]<0))
        if len(crossing)!=1:raise AssertionError(f'{name}: expected one unity crossing, got {len(crossing)}')
        i=int(crossing[0]);alpha=-gain[i]/(gain[i+1]-gain[i]);fu=np.exp(np.log(f[i])+alpha*np.log(f[i+1]/f[i]));pm=180+phase[i]+alpha*(phase[i+1]-phase[i])
        result.update(dc_gain_db=float(gain[0]),unity_hz=float(fu),phase_margin_deg=float(pm),dc_phase_deg=float(phase[0]))
        assert abs(phase[0])<1,'wrong loop polarity'
        assert result['power_w']>0,'wrong supply-current sign'
    elif mode=='noise':
        a=np.loadtxt(folder/'noise.dat',skiprows=1)
        result.update(input_noise_rms_v=float(np.sqrt(np.trapezoid(a[:,1]**2,a[:,0]))),noise_band_hz=[10,1e7],noise_1khz_v_sqrt_hz=float(np.interp(1000,a[:,0],a[:,1])))
    elif mode=='tran':
        a=np.loadtxt(folder/'tran.dat',skiprows=1);t=a[:,0];y=a[:,2]
        def settling(t0,t1,target):
            mask=(t>=t0)&(t<t1);tt=t[mask];yy=y[mask];bad=np.flatnonzero(abs(yy-target)>.01*abs(step))
            if len(bad)==0:return 0.
            k=int(bad[-1])+1
            if k>=len(tt):return None
            return float(tt[k]-t0)
        result.update(step_v=step,positive_settling_1pct_s=settling(1.001e-6,3e-6,cm+step),negative_settling_1pct_s=settling(3.001e-6,5e-6,cm-step))
        for label,t0,t1 in [('positive',1.001e-6,1.1e-6),('negative',3.001e-6,3.1e-6)]:
            m=(t>t0)&(t<t1);dy=np.gradient(y[m],t[m]);result[label+'_peak_slope_v_per_s']=float(np.max(dy) if label=='positive' else np.min(dy))
    return result

def figures():
    a=np.loadtxt(BUILD/'nominal/ac.dat',skiprows=1);h=a[:,1]+1j*a[:,2]
    fig,ax=plt.subplots(2,1,figsize=(8,6),sharex=True);ax[0].semilogx(a[:,0],20*np.log10(abs(h)));ax[0].axhline(0,color='gray',lw=.7);ax[0].set_ylabel('Open-loop gain (dB)');ax[1].semilogx(a[:,0],np.rad2deg(np.unwrap(np.angle(h))));ax[1].axhline(-180,color='gray',lw=.7);ax[1].set_ylabel('Phase (degrees)');ax[1].set_xlabel('Frequency (Hz)');[x.grid(True,alpha=.25) for x in ax];fig.tight_layout();fig.savefig(REPORTS/'bode.png',dpi=160);plt.close(fig)
    a=np.loadtxt(BUILD/'step/tran.dat',skiprows=1);fig,ax=plt.subplots(figsize=(8,3.5));ax.plot(a[:,0]*1e6,a[:,1],label='Input');ax.plot(a[:,0]*1e6,a[:,2],label='Output');ax.set(xlabel='Time (µs)',ylabel='Voltage (V)',title='Unity-gain follower, ±100 mV steps');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(REPORTS/'transient.png',dpi=160);plt.close(fig)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    REPORTS.mkdir(exist_ok=True)
    nominal=simulate('nominal');print('Nominal:',nominal,flush=True)
    noise=simulate('noise',mode='noise');step=simulate('step',mode='tran')
    conditions=list(itertools.product(['tt','ss','ff','sf','fs'],[1.71,1.8,1.89],[-40,27,85],[1e-12,2e-12,5e-12]))
    if args.quick:conditions=[('tt',1.8,27,2e-12),('ss',1.71,85,5e-12),('ff',1.89,-40,1e-12)]
    corners=[]
    for n,(c,v,t,cl) in enumerate(conditions):
        corners.append(simulate(f'pvt-{n:03}',c,v,t,cl));
        if n%15==0: print('PVT',n+1,'/',len(conditions),flush=True)
    compensation=[]
    for n,(cc,rz) in enumerate(itertools.product([.5e-12,1e-12,2e-12],[0.1,2000,5000])):
        compensation.append(simulate(f'comp-{n}',cc=cc,rz=rz))
    cm_results=[simulate(f'cm-{i}',mode='op',cm=float(v)) for i,v in enumerate(np.linspace(.5,1.3,9))]
    targets={'dc_gain_db_min':60,'unity_hz_min':5e6,'phase_margin_deg_min':50}
    for row in corners:
        row['meets_targets']=row['dc_gain_db']>=60 and row['unity_hz']>=5e6 and row['phase_margin_deg']>=50
    data={'simulator':subprocess.check_output(['ngspice','--version'],text=True).splitlines()[1].strip(),
          'circuit_sha256':hashlib.sha256((ROOT/'circuits/ota.spice').read_bytes()).hexdigest(),
          'nominal':nominal,'noise':noise,'transient':step,'targets':targets,'pvt_conditions':corners,
          'compensation_sweep':compensation,'common_mode_sweep':cm_results,
          'pvt_summary':{'count':len(corners),'meet_targets':sum(x['meets_targets'] for x in corners),
                         'gain_min_db':min(x['dc_gain_db'] for x in corners),'phase_margin_min_deg':min(x['phase_margin_deg'] for x in corners),
                         'unity_min_hz':min(x['unity_hz'] for x in corners)}}
    (REPORTS/'characterization.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');figures();print(data['pvt_summary'],flush=True)
if __name__=='__main__':main()
