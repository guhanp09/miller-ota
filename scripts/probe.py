from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
b=ROOT/'build';b.mkdir(exist_ok=True)
net=f'''OTA nominal probe
.option scale=1e-6
.include "{ROOT}/models/tt.spice"
.include "{ROOT}/circuits/ota.spice"
VDD vdd 0 1.8
VIN inp 0 dc 0.9 ac 1
* DC feedback closes bias; the 1 GH inductor opens it for AC analysis.
Lfb out inn 1G
Cac inn 0 1
Xamp inp inn out vdd 0 ota
CL out 0 2p
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
print v(out) v(xamp.mid) v(xamp.left) v(xamp.tail) i(vdd)
ac dec 80 1 1G
let re=real(v(out))
let im=imag(v(out))
wrdata {b}/ac.dat re im
noise v(out) VIN dec 40 10 100Meg
setplot noise1
wrdata {b}/noise.dat inoise_spectrum onoise_spectrum
quit
.endc
.end
'''
p=b/'probe.cir';p.write_text(net)
r=subprocess.run(['ngspice','-b',str(p)],cwd=ROOT,text=True,capture_output=True)
(b/'probe.log').write_text(r.stdout+r.stderr)
print(r.stdout[-2500:],r.stderr[-2500:]);print('rc',r.returncode)
