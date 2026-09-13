"""Temporal line-graph arcs: original edges become vertices."""
from dataclasses import dataclass
from itertools import combinations, product
import math
import ctypes
import tkinter as tk
from tkinter import ttk
from .evidence import references, milliseconds
from .theme import BG, FIELD, TEXT


@dataclass(frozen=True)
class TemporalArc:
    edge_a: str
    edge_b: str
    shared_nodes: tuple
    episode_a: str
    episode_b: str
    time_a: float
    time_b: float


def build_arcs(rows):
    records={row['edge_id']:row for row in rows}
    incident={}
    for key,row in records.items():
        for node in {row['from'],row['to']}:
            incident.setdefault(node,set()).add(key)
    pairs={}
    for node,edges in incident.items():
        for pair in combinations(sorted(edges),2):pairs.setdefault(pair,[]).append(node)
    centers={key:[(ref['episode'],(milliseconds(ref['start'])+milliseconds(ref['end']))/2000)
                  for ref in references(row)] for key,row in records.items()}
    arcs=[]
    for (a,b),shared in sorted(pairs.items()):
        for (ep_a,t_a),(ep_b,t_b) in product(centers[a],centers[b]):
            arcs.append(TemporalArc(a,b,tuple(sorted(shared)),ep_a,ep_b,t_a,t_b))
    return arcs


def bin_arcs(arcs, duration, pixel_width, bin_width=10):
    """Aggregate unordered endpoint-bin pairs in current canvas coordinates."""
    if duration<=0 or pixel_width<=0 or bin_width<=0:raise ValueError('Positive binning dimensions required')
    last=max(0,math.ceil(pixel_width/bin_width)-1)
    def index(t):return min(last,max(0,int(t/duration*pixel_width//bin_width)))
    groups={}
    for arc in arcs:
        pair=tuple(sorted((index(arc.time_a),index(arc.time_b))))
        group=groups.setdefault(pair,{'nodes':set(),'count':0})
        group['nodes'].update(arc.shared_nodes);group['count']+=1
    return groups


def timestamp(seconds):
    total=int(round(seconds*1000))
    h,rest=divmod(total,3600000);m,rest=divmod(rest,60000);s,ms=divmod(rest,1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


class ArcWindow(tk.Toplevel):
    def __init__(self,parent,rows):
        super().__init__(parent)
        self.title('Arc diagram');self.geometry('1400x850');self.configure(background=BG)
        self.rows={r['edge_id']:r for r in rows};self.arcs=build_arcs(rows)
        self.pending=None
        self.show_names=True
        self.bind('<KeyPress>',self.keypress)
        self.bind('<Escape>',lambda event:self.close())
        bar=ttk.Frame(self,padding=10);bar.pack(fill=tk.X)
        missing=sum(not references(r) for r in rows)
        self.count_text=tk.StringVar(value=f'{len(self.arcs)} raw arcs · {missing} edges without timestamps')
        ttk.Label(bar,textvariable=self.count_text).pack(side=tk.LEFT)
        self.zoom=tk.DoubleVar(value=1)
        ttk.Scale(bar,from_=1,to=8,variable=self.zoom,command=lambda value:self.schedule()).pack(side=tk.RIGHT)
        area=ttk.Frame(self);area.pack(fill=tk.BOTH,expand=True)
        self.canvas=tk.Canvas(area,background=FIELD,highlightthickness=0)
        scroll=ttk.Scrollbar(area,orient=tk.HORIZONTAL,command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=scroll.set)
        scroll.pack(side=tk.BOTTOM,fill=tk.X);self.canvas.pack(fill=tk.BOTH,expand=True)
        self.canvas.bind('<Configure>',lambda event:self.schedule())
        self.canvas.bind('<ButtonPress-1>',lambda event:self.canvas.scan_mark(event.x,event.y))
        self.canvas.bind('<B1-Motion>',lambda event:self.canvas.scan_dragto(event.x,event.y,gain=1))
        self.items={}
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.state('zoomed')
        self.bind('<Map>',self.activate_once,add='+')
        self.schedule()

    def activate_once(self,event):
        if event.widget is self and not getattr(self,'activated',False):
            self.activated=True
            self.lift();self.focus_force();self.canvas.focus_set()

    def keypress(self,event):
        # Physical N on Windows, independent of the input language and Num Lock.
        if event.state & 0x4 and not event.state & 0x20000:
            if ctypes.windll.user32.MapVirtualKeyW(event.keycode,0)==0x31:
                self.show_names=not self.show_names
                self.canvas.itemconfigure('arc-name',state='normal' if self.show_names else 'hidden')
                return 'break'

    def close(self):
        if self.pending is not None:self.after_cancel(self.pending)
        self.destroy()
        return 'break'

    def schedule(self):
        if self.pending is not None:self.after_cancel(self.pending)
        self.pending=self.after(150,self.draw)

    def draw(self):
        self.pending=None;self.canvas.delete('all');self.items={}
        width=max(600,self.canvas.winfo_width())*self.zoom.get()
        height=max(300,self.canvas.winfo_height());baseline=height-55
        self.canvas.configure(scrollregion=(0,0,width,height))
        if not self.arcs:
            self.canvas.create_text(30,40,anchor='nw',text='No adjacent edges with timestamp evidence in this view.',fill=TEXT,font=('Segoe UI',14))
            return
        times=[t for arc in self.arcs for t in (arc.time_a,arc.time_b)]
        end=max(max(times),1);left=65;right=width-65
        x=lambda t:left+t/end*(right-left)
        self.canvas.create_line(left,baseline,right,baseline,fill='#7b8494',width=2)
        for i in range(11):
            t=end*i/10;at=x(t)
            self.canvas.create_line(at,baseline,at,baseline+7,fill=TEXT,width=2)
            self.canvas.create_text(at,baseline+22,text=timestamp(t).split('.')[0],fill=TEXT,font=('Segoe UI',11))
        colors=('#789bea','#ad8cd6','#68b8ad','#d7a571','#cc8296')
        shared=sorted({node for arc in self.arcs for node in arc.shared_nodes})
        palette={node:colors[i%len(colors)] for i,node in enumerate(shared)}
        groups=bin_arcs(self.arcs,end,right-left)
        self.count_text.set(f'{len(groups)} binned arcs · {len(self.arcs)} raw arcs · 10 px bins')
        def center(index):
            lo=index*10;hi=min(lo+10,right-left)
            return left+(lo+hi)/2
        for (bin_a,bin_b),group in sorted(groups.items(),key=lambda item:item[0][1]-item[0][0],reverse=True):
            a,b=center(bin_a),center(bin_b)
            rise=min(max((b-a)/2,16),baseline-30)
            if bin_a==bin_b:a-=4;b+=4
            names=sorted(group['nodes'])
            color=palette[names[0]] if len(names)==1 else '#929baa'
            self.canvas.create_arc(a,baseline-rise,b,baseline+rise,start=0,extent=180,
                                   style=tk.ARC,outline=color,width=1)
            self.canvas.create_text((a+b)/2,baseline-rise-5,anchor='s',
                text=', '.join(names),fill=color,
                font=('Segoe UI',11),tags=('arc-name',),state='normal' if self.show_names else 'hidden')
        self.canvas.tag_raise('arc-name')
        for index in {i for pair in groups for i in pair}:
            at=center(index);self.canvas.create_oval(at-3,baseline-3,at+3,baseline+3,fill=TEXT,outline='')

