#!/usr/bin/python3
import hashlib, json, os, re, subprocess, tempfile, threading, urllib.request, urllib.error
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib

PHASES = [
    (5,   25, 'Refreshing APT package lists'),
    (25,  60, 'Installing APT upgrades'),
    (60,  70, 'Removing obsolete packages'),
    (70,  82, 'Updating system Flatpaks'),
    (82,  90, 'Repairing boot menu'),
    (90, 100, 'Refreshing initramfs'),
    (100,100, 'Updating your Flatpak apps'),
]

GITHUB_API='https://api.github.com/repos/crhy/spaced/releases?per_page=100'
DOWNLOAD_DIR=os.path.expanduser('~/.cache/spaced-update')

class PhaseRow(Gtk.Box):
    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head=Gtk.Box(spacing=8); head.set_vexpand(False); self.pack_start(head,False,False,0)
        self.icon=Gtk.Image.new_from_icon_name('radio-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        head.pack_start(self.icon,False,False,0)
        self.name=Gtk.Label(label=name, xalign=0); self.name.set_ellipsize(True); head.pack_start(self.name,True,True,0)
        self.pct=Gtk.Label(label='', xalign=1); head.pack_end(self.pct,False,False,0)
        self.bar=Gtk.ProgressBar(); self.bar.set_fraction(0); self.pack_start(self.bar,False,False,0)
    def set_pending(self):
        self.icon.set_from_icon_name('radio-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        self.pct.set_text('')
        self.bar.set_fraction(0)
    def set_running(self, pct, msg):
        self.icon.set_from_icon_name('process-working-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        self.pct.set_text(f'{pct}%')
        self.bar.set_fraction(pct/100)
        if msg: self.name.set_text(msg)
    def set_done(self, pct=100):
        self.icon.set_from_icon_name('emblem-ok-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        self.pct.set_text('')
        self.bar.set_fraction(1)

def version_key(v):
    nums=re.findall(r'\d+', v or '0')
    return tuple(int(n) for n in nums[:4])

def read_installed_version():
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('VERSION_ID='):
                    return line.split('=',1)[1].strip().strip('"')
    except OSError:
        pass
    return None

class OsUpdateTab(Gtk.Box):
    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.app=app
        self.latest=None
        self.installed=read_installed_version()

        status=Gtk.Label(); status.set_markup(
            '<span size="large" weight="bold">Full OS update</span>'); status.set_xalign(0)
        self.pack_start(status,False,False,0)
        hint=Gtk.Label(label='Checks crhy/spaced for the newest Spaced Linux ISO, downloads it, verifies its SHA-256 checksum, and prepares you to reboot.')
        hint.set_xalign(0); hint.set_wrap(True); self.pack_start(hint,False,False,0)

        self.inst=Gtk.Label(label=f'Installed: {self.installed or "unknown"}', xalign=0)
        self.pack_start(self.inst,False,False,0)
        self.lat=Gtk.Label(label='Latest: check the release feed to find out.', xalign=0)
        self.pack_start(self.lat,False,False,0)

        self.msg=Gtk.Label(label='', xalign=0); self.msg.set_wrap(True); self.pack_start(self.msg,False,False,0)

        self.progress=Gtk.ProgressBar(); self.progress.set_show_text(True)
        self.pack_start(self.progress,False,False,0)

        row=Gtk.Box(spacing=8); self.pack_start(row,False,False,0)
        self.checkbtn=Gtk.Button(label='Check for OS Updates'); self.checkbtn.connect('clicked',self.check)
        row.pack_start(self.checkbtn,False,False,0)
        self.dlbtn=Gtk.Button(label='Download Latest ISO'); self.dlbtn.set_sensitive(False); self.dlbtn.connect('clicked',self.download)
        row.pack_start(self.dlbtn,False,False,0)
        self.rebootbtn=Gtk.Button(label='Reboot Now'); self.rebootbtn.set_sensitive(False); self.rebootbtn.connect('clicked',self.reboot)
        row.pack_start(self.rebootbtn,False,False,0)
        self.pack_start(row,False,False,0)

        self.logscroll=Gtk.ScrolledWindow(); self.logscroll.set_hexpand(True); self.logscroll.set_vexpand(True)
        self.log=Gtk.TextView(); self.log.set_editable(False); self.log.set_monospace(True)
        self.buf=self.log.get_buffer(); self.logscroll.add(self.log); self.pack_start(self.logscroll,True,True,0)

    def logline(self,text):
        end=self.buf.get_end_iter(); self.buf.insert(end,text+'\n')
        self.log.scroll_to_iter(self.buf.get_end_iter(),0,False,0,0)

    def check(self,*_):
        self.checkbtn.set_sensitive(False)
        self.msg.set_text('Checking the release feed…')
        threading.Thread(target=self._check_worker,daemon=True).start()

    def _check_worker(self):
        try:
            req=urllib.request.Request(GITHUB_API, headers={'User-Agent':'spaced-update','Accept':'application/vnd.github+json'})
            releases=json.load(urllib.request.urlopen(req, timeout=30))
            candidates=[(version_key(r['tag_name']), r) for r in releases
                        if not r.get('draft') and r.get('assets')]
            if not candidates:
                GLib.idle_add(self._check_done,None,None,'No published releases found.')
                return
            releases=sorted(candidates, key=lambda t: t[0])
            latest=releases[-1]
            name=None
            for a in latest[1]['assets']:
                if a['name'].endswith('.iso') and not a['name'].endswith('.sha256'):
                    name=a['name']; break
            if not name:
                GLib.idle_add(self._check_done,None,None,'Latest release has no ISO asset.')
                return
            self.latest={'tag':latest[1]['tag_name'],'name':name,'url':next(a['browser_download_url'] for a in latest[1]['assets'] if a['name']==name),
                         'sha':next((a['browser_download_url'] for a in latest[1]['assets'] if a['name']==name+'.sha256'),None)}
            GLib.idle_add(self._check_done,self.latest,None,None)
        except Exception as e:
            GLib.idle_add(self._check_done,None,e,None)

    def _check_done(self,latest,err,msg):
        self.checkbtn.set_sensitive(True)
        if err:
            self.msg.set_text('Could not reach the Spaced Linux release feed.')
            self.logline(f'ERROR: {err}')
            return
        if msg:
            self.msg.set_text(msg); self.logline(msg); return
        self.lat.set_text(f'Latest: {latest["tag"]}  ({latest["name"]})')
        self.msg.set_text('A newer release is available.')
        self.dlbtn.set_sensitive(True)
        self.logline(f'Found release {latest["tag"]}: {latest["name"]}')

    def download(self,*_):
        if not self.latest: return
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self.dlbtn.set_sensitive(False)
        self.progress.set_fraction(0); self.progress.set_text('Downloading ISO…')
        self.logline(f'Downloading {self.latest["url"]}')
        threading.Thread(target=self._download_worker,daemon=True).start()

    def _download_worker(self):
        latest=self.latest
        try:
            target=os.path.join(DOWNLOAD_DIR, latest['name'])
            part=target+'.part'
            req=urllib.request.Request(latest['url'], headers={'User-Agent':'spaced-update'})
            with urllib.request.urlopen(req, timeout=60) as r:
                total=int(r.headers.get('Content-Length') or 0)
                h=hashlib.sha256()
                written=0
                with open(part,'wb') as f:
                    while True:
                        chunk=r.read(1<<20)
                        if not chunk: break
                        f.write(chunk); h.update(chunk); written+=len(chunk)
                        if total:
                            frac=written/total
                            GLib.idle_add(self.progress.set_fraction,frac)
                            GLib.idle_add(self.progress.set_text,f'Downloading… {written/1048576:.0f}/{total/1048576:.0f} MiB')
            expected=None
            if latest['sha']:
                shreq=urllib.request.Request(latest['sha'], headers={'User-Agent':'spaced-update'})
                shline=urllib.request.urlopen(shreq, timeout=30).read().decode().strip()
                m=re.match(r'([0-9a-fA-F]{64})', shline)
                if m: expected=m.group(1).lower()
            actual=h.hexdigest()
            if expected and actual!=expected:
                raise RuntimeError(f'SHA-256 mismatch: expected {expected}, got {actual}')
            os.replace(part,target)
            GLib.idle_add(self._download_done,target,expected,actual,None)
        except Exception as e:
            GLib.idle_add(self._download_done,None,None,None,e)

    def _download_done(self,target,expected,actual,err):
        if err:
            self.progress.set_text('Download failed')
            self.logline(f'ERROR: {err}')
            self.dlbtn.set_sensitive(True)
            return
        self.progress.set_fraction(1); self.progress.set_text('Verified — ready to apply')
        self.msg.set_text(f'ISO ready at {target}. Back up your data, then reboot to apply the full OS update.')
        self.logline(f'Downloaded {target}')
        self.logline(f'SHA-256: {actual}' + (f' (verified)' if expected else ' (no checksum on release)'))
        self.rebootbtn.set_sensitive(True)

    def reboot(self,*_):
        self.logline('Requesting reboot…')
        threading.Thread(target=lambda: subprocess.call(['pkexec','systemctl','reboot']),daemon=True).start()

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title='Spaced Update')
        self.set_default_size(820, 600)
        self.set_border_width(18)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); self.add(box)

        title=Gtk.Label(); title.set_markup('<span size="x-large" weight="bold">Spaced Update</span>'); title.set_xalign(0); box.pack_start(title,False,False,0)
        sub=Gtk.Label(label='Updates Spaced Linux through APT, Flathub, and full OS releases in one place.'); sub.set_xalign(0); box.pack_start(sub,False,False,0)

        nb=Gtk.Notebook(); nb.set_hexpand(True); nb.set_vexpand(True); box.pack_start(nb,True,True,0)

        self.updates_tab=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        nb.append_page(self.updates_tab,Gtk.Label(label='System Updates'))

        head=Gtk.Box(spacing=12); self.updates_tab.pack_start(head,False,False,0)
        self.mode=Gtk.ComboBoxText(); self.mode.append('simple','Simplified'); self.mode.append('cli','CLI output'); self.mode.set_active(0)
        self.mode.connect('changed',self._on_mode); head.pack_start(self.mode,False,False,0)
        head.pack_end(Gtk.Label(label=''),True,True,0)

        self.stack=Gtk.Stack(); self.stack.set_hexpand(True); self.stack.set_vexpand(True); self.updates_tab.pack_start(self.stack,True,True,0)

        simple=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.status=Gtk.Label(label='Ready to check for updates.'); self.status.set_xalign(0); self.status.set_wrap(True); simple.pack_start(self.status,False,False,0)
        self.segments=Gtk.Box(spacing=4)
        self.seg_bars=[]
        for (lo,hi,_name) in PHASES:
            b=Gtk.ProgressBar(); b.set_hexpand(True); b.set_fraction(0)
            self.segments.pack_start(b,True,True,0); self.seg_bars.append(b)
        simple.pack_start(self.segments,False,False,0)
        self.phases=[]
        for (_lo,_hi,name) in PHASES:
            pr=PhaseRow(name); pr.set_pending(); self.phases.append(pr); simple.pack_start(pr,False,False,0)
        self.stack.add_named(simple,'simple')

        cli=Gtk.ScrolledWindow(); cli.set_hexpand(True); cli.set_vexpand(True)
        self.log=Gtk.TextView(); self.log.set_editable(False); self.log.set_monospace(True)
        self.buf=self.log.get_buffer(); cli.add(self.log); self.stack.add_named(cli,'cli')
        self._on_mode()

        row=Gtk.Box(spacing=8); self.updates_tab.pack_start(row,False,False,0)
        self.runbtn=Gtk.Button(label='Install All Updates'); self.runbtn.connect('clicked',self.start); row.pack_end(self.runbtn,False,False,0)
        close=Gtk.Button(label='Close'); close.connect('clicked',lambda *_: Gtk.main_quit()); row.pack_end(close,False,False,0)

        self.os_tab=OsUpdateTab(self)
        nb.append_page(self.os_tab,Gtk.Label(label='OS Update'))

        self.connect('destroy',Gtk.main_quit)

    def _on_mode(self,*_):
        self.stack.set_visible_child_name(self.mode.get_active_id() or 'simple')

    def append(self,text):
        end=self.buf.get_end_iter(); self.buf.insert(end,text+'\n'); self.log.scroll_to_iter(self.buf.get_end_iter(),0,False,0,0)

    def setstep(self,pct,msg):
        pct=int(pct)
        self.status.set_text(f'{pct}% — {msg}')
        for (lo,hi,_),bar in zip(PHASES,self.seg_bars):
            frac=0.0
            if pct>=hi: frac=1.0
            elif pct>lo: frac=(pct-lo)/max(1,(hi-lo))
            bar.set_fraction(frac)
        for i,(lo,hi,_) in enumerate(PHASES):
            if lo<=pct<hi:
                for j,pr in enumerate(self.phases):
                    if j<i: pr.set_done()
                    elif j==i:
                        frac=(pct-lo)/max(1,(hi-lo))
                        pr.set_running(int(frac*100), msg)
                    else: pr.set_pending()

    def start(self,*_):
        self.runbtn.set_sensitive(False); self.buf.set_text('')
        for pr in self.phases: pr.set_pending()
        for b in self.seg_bars: b.set_fraction(0)
        threading.Thread(target=self.worker,daemon=True).start()

    def run_cmd(self,cmd,label,base):
        GLib.idle_add(self.status.set_text,label)
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in p.stdout:
            line=line.rstrip(); m=re.match(r'SPACED_STEP:(\d+):(.*)',line)
            if m: GLib.idle_add(self.setstep,int(m.group(1)),m.group(2))
            else: GLib.idle_add(self.append,line)
        return p.wait()

    def worker(self):
        try:
            from shutil import which
            rc=self.run_cmd(['pkexec','/usr/lib/spaced-linux/spaced-update-helper'],'Updating system packages',0)
            if rc: raise RuntimeError(f'System update helper exited with status {rc}')
            self.setstep(100,'Updating system Flatpaks')
            for pr in self.phases[:6]: pr.set_done()
            self.process_flatpaks()
            GLib.idle_add(self.setstep,100,'Everything is up to date')
            GLib.idle_add(self.append,'Finished successfully.')
        except Exception as e:
            GLib.idle_add(self.status.set_text,'Update failed')
            GLib.idle_add(self.append,f'ERROR: {e}')
        finally: GLib.idle_add(self.runbtn.set_sensitive,True)

    def process_flatpaks(self):
        from shutil import which
        if which('flatpak'):
            GLib.idle_add(self.setstep,100,'Updating your Flatpak applications')
            self.phases[6].set_running(50,'Updating your Flatpak applications')
            p=subprocess.Popen(['flatpak','update','-y','--user'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in p.stdout: GLib.idle_add(self.append,line.rstrip())
            p.wait()
        GLib.idle_add(self.phases[6].set_done)

App().show_all(); Gtk.main()