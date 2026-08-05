#!/usr/bin/python3
import json, re, subprocess, threading, urllib.request
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib

GITHUB_API='https://api.github.com/repos/crhy/spaced/releases?per_page=100'

APT_RE=re.compile(r'^(\S+?)/\S+\s+(\S+)\s+\S+\s+\[upgradable from:\s+(.+)\]$')

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

def enumerate_apt():
    try:
        out=subprocess.run(['apt','list','--upgradable'],capture_output=True,text=True,timeout=60).stdout
    except Exception:
        return []
    items=[]
    for line in out.splitlines():
        m=APT_RE.match(line.strip())
        if m:
            items.append({'kind':'apt','name':m.group(1),'cur':m.group(3),'new':m.group(2)})
    return sorted(items,key=lambda i:i['name'])

def enumerate_flatpak():
    try:
        listed=subprocess.run(['flatpak','list','--app','--columns=application'],capture_output=True,text=True,timeout=60).stdout
        upd=subprocess.run(['flatpak','remote-ls','--updates','--columns=ref'],capture_output=True,text=True,timeout=60).stdout
        names=subprocess.run(['flatpak','list','--app','--columns=application,name'],capture_output=True,text=True,timeout=60).stdout
    except Exception:
        return []
    installed={l.split()[0] for l in listed.splitlines() if l.strip()}
    name_map=dict((l.split()[0],' '.join(l.split()[1:])) for l in names.splitlines() if l.strip() and '\t' in l)
    items=[]
    for line in upd.splitlines():
        line=line.strip()
        if not line.startswith('app/'): continue
        ref=line[4:]
        app_id=ref.split('/')[0]
        if app_id not in installed: continue
        items.append({'kind':'flatpak','name':app_id,'cur':None,'new':None,'display':name_map.get(app_id,app_id)})
    return sorted(items,key=lambda i:i['display'])

class UpdateRow(Gtk.CheckButton):
    def __init__(self,item):
        self.item=item
        if item['kind']=='apt':
            label=f"{item['name']}  ({item['cur']} → {item['new']})"
        else:
            label=f"{item['display']}  ({item['name']})"
        super().__init__(label=label, hexpand=True, xalign=0)
        self.set_margin_bottom(2)

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title='Spaced Update')
        self.set_default_size(820, 620)
        self.set_border_width(18)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); self.add(box)

        title=Gtk.Label(); title.set_markup('<span size="x-large" weight="bold">Spaced Update</span>'); title.set_xalign(0); box.pack_start(title,False,False,0)
        sub=Gtk.Label(label='Updates Spaced Linux through APT, Flathub, and full OS releases in one place.'); sub.set_xalign(0); box.pack_start(sub,False,False,0)

        nb=Gtk.Notebook(); nb.set_hexpand(True); nb.set_vexpand(True); box.pack_start(nb,True,True,0)

        # ---------------- System Updates tab ----------------
        utab=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        nb.append_page(utab,Gtk.Label(label='System Updates'))

        toolbar=Gtk.Box(spacing=8); utab.pack_start(toolbar,False,False,0)
        self.checkbtn=Gtk.Button(label='Check for Updates'); self.checkbtn.connect('clicked',self.do_check); toolbar.pack_start(self.checkbtn,False,False,0)
        self.selectall=Gtk.CheckButton(label='Select all'); self.selectall.set_sensitive(False); self.selectall.connect('toggled',self.on_select_all); toolbar.pack_start(self.selectall,False,False,0)
        self.status=Gtk.Label(label='Click Check for Updates to see what is available.'); self.status.set_xalign(0); toolbar.pack_start(self.status,True,True,0)
        self.mode=Gtk.ComboBoxText(); self.mode.append('progress','Progress'); self.mode.append('cli','CLI output'); self.mode.set_active(0)
        self.mode.connect('changed',self._on_mode); toolbar.pack_end(self.mode,False,False,0)

        self.stack=Gtk.Stack(); self.stack.set_hexpand(True); self.stack.set_vexpand(True); utab.pack_start(self.stack,True,True,0)

        # list view
        self.listscroll=Gtk.ScrolledWindow(); self.listscroll.set_hexpand(True); self.listscroll.set_vexpand(True)
        self.listbox=Gtk.ListBox(); self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listscroll.add(self.listbox); self.stack.add_named(self.listscroll,'list')

        # progress view
        prog=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.pstatus=Gtk.Label(label=''); self.pstatus.set_xalign(0); self.pstatus.set_line_wrap(True); prog.pack_start(self.pstatus,False,False,0)
        self.pbar=Gtk.ProgressBar(); self.pbar.set_show_text(True); prog.pack_start(self.pbar,False,False,0)
        plog=Gtk.ScrolledWindow(); plog.set_hexpand(True); plog.set_vexpand(True)
        self.plog=Gtk.TextView(); self.plog.set_editable(False); self.plog.set_monospace(True)
        self.pbuf=self.plog.get_buffer(); plog.add(self.plog); prog.pack_start(plog,True,True,0)
        self.stack.add_named(prog,'progress')

        # cli view
        cli=Gtk.ScrolledWindow(); cli.set_hexpand(True); cli.set_vexpand(True)
        self.cli=Gtk.TextView(); self.cli.set_editable(False); self.cli.set_monospace(True)
        self.clibuf=self.cli.get_buffer(); cli.add(self.cli); self.stack.add_named(cli,'cli')

        bottom=Gtk.Box(spacing=8); utab.pack_start(bottom,False,False,0)
        self.runbtn=Gtk.Button(label='Install Selected'); self.runbtn.set_sensitive(False); self.runbtn.connect('clicked',self.do_install); bottom.pack_end(self.runbtn,False,False,0)
        close=Gtk.Button(label='Close'); close.connect('clicked',lambda *_: Gtk.main_quit()); bottom.pack_end(close,False,False,0)
        self._on_mode()

        # ---------------- OS Update tab ----------------
        self.os_tab=OsUpdateTab(self)
        nb.append_page(self.os_tab,Gtk.Label(label='OS Update'))

        self.connect('destroy',Gtk.main_quit)

    def _on_mode(self,*_):
        self.stack.set_visible_child_name(self.mode.get_active_id() or 'progress')

    def logline(self,text):
        end=self.pbuf.get_end_iter(); self.pbuf.insert(end,text+'\n')
        self.plog.scroll_to_iter(self.pbuf.get_end_iter(),0,False,0,0)
        end=self.clibuf.get_end_iter(); self.clibuf.insert(end,text+'\n')
        self.cli.scroll_to_iter(self.clibuf.get_end_iter(),0,False,0,0)

    def setstep(self,pct,msg):
        self.pstatus.set_text(f'{pct}% — {msg}')
        self.pbar.set_fraction(pct/100); self.pbar.set_text(f'{pct}%')

    def show_view(self,name):
        self.stack.set_visible_child_name(name)
        if name=='progress': self.mode.set_active_id('progress')
        elif name=='cli': self.mode.set_active_id('cli')

    def do_check(self,*_):
        self.checkbtn.set_sensitive(False)
        self.selectall.set_active(False); self.selectall.set_sensitive(False)
        self.runbtn.set_sensitive(False)
        self._clear_list()
        self.status.set_text('Checking for updates…')
        self.show_view('list')
        threading.Thread(target=self._check_worker,daemon=True).start()

    def _clear_list(self):
        for row in self.listbox.get_children(): self.listbox.remove(row)
        self._apt_rows=[]; self._fp_rows=[]

    def _check_worker(self):
        try:
            apt=enumerate_apt(); fp=enumerate_flatpak()
            GLib.idle_add(self._check_done,apt,fp,None)
        except Exception as e:
            GLib.idle_add(self._check_done,[],[],e)

    def _add_section(self,label):
        lab=Gtk.Label(); lab.set_markup(f'<b>{label}</b>'); lab.set_xalign(0); lab.set_margin_top(8); lab.set_margin_bottom(2)
        self.listbox.add(lab)

    def _check_done(self,apt,fp,err):
        self.checkbtn.set_sensitive(True)
        if err:
            self.status.set_text('Could not check for updates.')
            self.logline(f'ERROR: {err}')
            return
        self._clear_list()
        if apt:
            self._add_section(f'APT packages ({len(apt)})')
            self._apt_rows=[]
            for it in apt:
                r=UpdateRow(it); self._apt_rows.append(r); self.listbox.add(r)
        if fp:
            self._add_section(f'Flatpak applications ({len(fp)})')
            self._fp_rows=[]
            for it in fp:
                r=UpdateRow(it); self._fp_rows.append(r); self.listbox.add(r)
        self.listbox.show_all()
        total=len(apt)+len(fp)
        if total==0:
            self.status.set_text('Your system is up to date. No updates available.')
            self.selectall.set_sensitive(False)
            self.runbtn.set_sensitive(False)
        else:
            self.status.set_text(f'{total} update(s) available. Select which to install.')
            self.selectall.set_sensitive(True)
            self.runbtn.set_sensitive(True)

    def on_select_all(self,*_):
        want=self.selectall.get_active()
        for r in self._apt_rows+self._fp_rows: r.set_active(want)

    def selected_items(self):
        return [r.item for r in self._apt_rows+self._fp_rows if r.get_active()]

    def do_install(self,*_):
        items=self.selected_items()
        if not items: return
        self.runbtn.set_sensitive(False); self.selectall.set_sensitive(False); self.checkbtn.set_sensitive(False)
        self.pbar.set_fraction(0); self.pbuf.set_text(''); self.clibuf.set_text('')
        self.show_view('progress')
        threading.Thread(target=lambda: self._install_worker(items),daemon=True).start()

    def _install_worker(self,items):
        apt=[i['name'] for i in items if i['kind']=='apt']
        fp=[i['name'] for i in items if i['kind']=='flatpak']
        try:
            GLib.idle_add(self.setstep,0,'Preparing')
            if apt:
                GLib.idle_add(self.logline,f'Installing {len(apt)} package(s): '+', '.join(apt))
                rc=self.run_cmd(['pkexec','/usr/lib/spaced-linux/spaced-update-helper','apt-install']+apt,'Installing selected packages')
                if rc: raise RuntimeError(f'Package install exited with status {rc}')
            if fp:
                GLib.idle_add(self.logline,f'Updating {len(fp)} application(s): '+', '.join(fp))
                rc=self.run_cmd(['pkexec','/usr/lib/spaced-linux/spaced-update-helper','flatpak-update']+fp,'Updating selected Flatpak applications')
                if rc: raise RuntimeError(f'Flatpak update exited with status {rc}')
            GLib.idle_add(self.setstep,100,'Done')
            GLib.idle_add(self.logline,'Finished successfully.')
            GLib.idle_add(self.status.set_text,'Updates installed successfully.')
        except Exception as e:
            GLib.idle_add(self.setstep,0,'Update failed')
            GLib.idle_add(self.logline,f'ERROR: {e}')
        finally:
            GLib.idle_add(self.runbtn.set_sensitive,True)
            GLib.idle_add(self.selectall.set_sensitive,True)
            GLib.idle_add(self.checkbtn.set_sensitive,True)

    def run_cmd(self,cmd,label,log_cb=None):
        if not log_cb: log_cb=self.logline
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in p.stdout:
            line=line.rstrip(); m=re.match(r'SPACED_STEP:(\d+):(.*)',line)
            if m: GLib.idle_add(self.setstep,int(m.group(1)),m.group(2))
            else: GLib.idle_add(log_cb,line)
        return p.wait()

    def do_os_update(self,*_):
        tab=self.os_tab
        tab.updatebtn.set_sensitive(False)
        GLib.idle_add(tab.logline,'Applying OS update through package repositories…')
        threading.Thread(target=self._os_update_worker,daemon=True).start()

    def _os_update_worker(self):
        tab=self.os_tab
        try:
            rc=self.run_cmd(['pkexec','/usr/lib/spaced-linux/spaced-update-helper'],
                            'Updating system to the latest OS version', tab.logline)
            if rc: raise RuntimeError(f'System update helper exited with status {rc}')
            GLib.idle_add(tab.msg.set_text,'Your system is updated. A reboot is recommended.')
            GLib.idle_add(tab.logline,'Finished successfully.')
        except Exception as e:
            GLib.idle_add(tab.logline,f'ERROR: {e}')
        finally:
            GLib.idle_add(tab.updatebtn.set_sensitive,True)

class OsUpdateTab(Gtk.Box):
    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.app=app
        self.installed=read_installed_version()

        status=Gtk.Label(); status.set_markup('<span size="large" weight="bold">Full OS update</span>'); status.set_xalign(0)
        self.pack_start(status,False,False,0)
        hint=Gtk.Label(label='Checks crhy/spaced for a newer Spaced Linux version. Spaced is a rolling release, so OS updates are delivered through the package repositories — no ISO download required.')
        hint.set_xalign(0); hint.set_line_wrap(True); self.pack_start(hint,False,False,0)

        self.inst=Gtk.Label(label=f'Installed: {self.installed or "unknown"}', xalign=0); self.pack_start(self.inst,False,False,0)
        self.lat=Gtk.Label(label='Latest: check the release feed to find out.', xalign=0); self.pack_start(self.lat,False,False,0)
        self.msg=Gtk.Label(label='', xalign=0); self.msg.set_line_wrap(True); self.pack_start(self.msg,False,False,0)

        row=Gtk.Box(spacing=8); self.pack_start(row,False,False,0)
        self.checkbtn=Gtk.Button(label='Check for OS Updates'); self.checkbtn.connect('clicked',self.check); row.pack_start(self.checkbtn,False,False,0)
        self.updatebtn=Gtk.Button(label='Update to Latest Version'); self.updatebtn.set_sensitive(False); self.updatebtn.connect('clicked',self.app.do_os_update); row.pack_start(self.updatebtn,False,False,0)
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
            candidates=[(version_key(r['tag_name']), r) for r in releases if not r.get('draft') and r.get('assets')]
            if not candidates:
                GLib.idle_add(self._check_done,None,None,'No published releases found.')
                return
            latest=sorted(candidates, key=lambda t: t[0])[-1]
            GLib.idle_add(self._check_done,{'tag':latest[1]['tag_name']},None,None)
        except Exception as e:
            GLib.idle_add(self._check_done,None,e,None)

    def _check_done(self,latest,err,msg=None):
        self.checkbtn.set_sensitive(True)
        if err:
            self.msg.set_text('Could not reach the Spaced Linux release feed.')
            self.logline(f'ERROR: {err}')
            return
        if msg:
            self.msg.set_text(msg); self.logline(msg); return
        self.lat.set_text(f'Latest: {latest["tag"]}')
        if self.installed and version_key(latest['tag']) > version_key(self.installed):
            self.msg.set_text('A newer Spaced Linux version is available. It will be installed from the package repositories.')
            self.updatebtn.set_sensitive(True)
            self.logline(f'Newer version available: {latest["tag"]}')
        elif self.installed and version_key(latest['tag']) <= version_key(self.installed):
            self.msg.set_text('Your system is up to date. Repositories already carry the latest release.')
        else:
            self.msg.set_text('Installed version unknown; update through the System Updates tab regardless.')

App().show_all(); Gtk.main()