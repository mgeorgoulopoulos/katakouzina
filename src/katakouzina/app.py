import json
import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from .positions import PositionStore
from .arcs import ArcWindow
from .deletions import DeletionStore
from .topology import edit as edit_topology, node_names, nearest_nodes
from .special_nodes import load_special_nodes
from .config import save_preferences
from .graph import discover, load_edges, project, layout

from .inspector import Inspector
from .review import ReviewStore
from .evidence import EvidenceLibrary
from .theme import apply_dark, edge_color, FIELD, TEXT
from .shortcuts import install as install_shortcuts

class GraphBrowser(Inspector, tk.Tk):
    def __init__(self, data_dir, preferences=None, config_root=None):
        super().__init__()
        self.preferences=preferences or {}
        self.config_root=config_root
        apply_dark(self)
        self.title('Katakouzina — Episode graphs')
        self.geometry('1700x950'); self.minsize(1200, 650)
        self.label_font = tkfont.Font(root=self, family='Segoe UI', size=self.preferences.get('graph_font_size',18))
        self.show_node_names=True
        self.all_positions={}
        self.position_store=None;self.position_key=None;self.position_save_job=None
        self.protocol("WM_DELETE_WINDOW",self.close_app)
        self.evidence_library=EvidenceLibrary(data_dir)
        self.deleted_nodes=set();self.deleted_edges=set()
        self.rejected_reasons = {}
        self.verified_ids = set(); self.review_store = None
        self.show_rejected=tk.BooleanVar(value=self.preferences.get('show_rejected_edges',False))
        self.hops_enabled=tk.BooleanVar(value=False)
        self.whole_view=None
        self.special_node_colors=load_special_nodes(data_dir)
        self.data_dir = data_dir
        self.tree_nodes = {}; self.pending_tree_node = None
        self.paths = {}; self.rows = []; self.graph = None; self.positions = {}; self.normalized = {}
        self.items = {}; self.drag_node = None; self.drag_origin = None; self.selected_node = None
        self.generation = 0; self.results = queue.Queue(); self.current_path = None
        self.status_filter = tk.StringVar(value='ALL'); self.layer_filter = tk.StringVar(value='ALL')
        self.hide_leaves = tk.BooleanVar(value=self.preferences.get('hide_leaves',False)); self.focus_text = tk.StringVar()
        self.notice = tk.StringVar(value='')
        self.build_ui(); self.refresh(); self.after(100, self.poll)
        self.report_callback_exception = self.on_callback_error
        install_shortcuts(self)

    def toggle_rejected_visibility(self,event=None):
        self.show_rejected.set(not self.show_rejected.get())
        self.render()
        return 'break'

    def build_ui(self):
        menu=tk.Menu(self,tearoff=False)
        view=tk.Menu(menu,tearoff=False)
        view.add_checkbutton(label='Show human-rejected edges',variable=self.show_rejected,command=self.render,accelerator='Ctrl+J')
        view.add_checkbutton(label='Hide global leaves',variable=self.hide_leaves,command=self.render,accelerator='Ctrl+L')
        view.add_checkbutton(label='2-hop view',variable=self.hops_enabled,command=self.menu_hops,accelerator='Ctrl+H')
        menu.add_cascade(label='View',menu=view)
        tools=tk.Menu(menu,tearoff=False)
        tools.add_command(label='Arc diagram',command=self.open_arc_diagram)
        menu.add_cascade(label='Tools',menu=tools)
        self.configure(menu=menu)

        outer = ttk.Panedwindow(self, orient=tk.HORIZONTAL); outer.pack(fill=tk.BOTH, expand=True)
        sidebar = ttk.Frame(outer, padding=8); outer.add(sidebar, weight=0)
        ttk.Label(sidebar, text='Episodes / graphs').pack(anchor='w', pady=(0,8))
        self.tree = ttk.Treeview(sidebar, show='tree', selectmode='browse')
        self.tree.column('#0', width=220, minwidth=140)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.select_graph)
        ttk.Button(sidebar, text='Refresh episodes', command=self.refresh).pack(fill=tk.X, pady=(8,0))
        right = ttk.Frame(outer); outer.add(right, weight=1)
        toolbar = ttk.Frame(right, padding=8); toolbar.pack(fill=tk.X)
        ttk.Label(toolbar, text='Layer').pack(side=tk.LEFT)
        self.layers = ttk.Combobox(toolbar, textvariable=self.layer_filter, values=('ALL',), state='readonly', width=13)
        self.layers.pack(side=tk.LEFT, padx=5); self.layers.bind('<<ComboboxSelected>>', lambda e:self.render())
        ttk.Checkbutton(toolbar, text='Hide global leaves', variable=self.hide_leaves, command=self.render).pack(side=tk.LEFT,padx=5)
        ttk.Button(toolbar, text='Fit', command=self.fit).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text='Tidy (Ctrl+T)', command=self.auto_arrange).pack(side=tk.RIGHT, padx=5)
        focusbar = ttk.Frame(right, padding=(8,0,8,8)); focusbar.pack(fill=tk.X)
        ttk.Label(focusbar, text='Node').pack(side=tk.LEFT)
        self.nodes = ttk.Combobox(focusbar, textvariable=self.focus_text, width=30)
        self.nodes.pack(side=tk.LEFT,padx=5)
        ttk.Button(focusbar, text='Toggle 2 hops (Ctrl+H)', command=self.toggle_hops).pack(side=tk.LEFT)
        ttk.Button(focusbar, text='Whole graph', command=self.clear_focus).pack(side=tk.LEFT,padx=5)
        self.canvas = tk.Canvas(right, background=FIELD, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-3>',self.context_menu)
        self.canvas.bind('<ButtonPress-1>',self.press); self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag_origin',None))
        self.canvas.bind('<MouseWheel>',self.zoom)
        self.canvas.bind('<Button-4>',lambda e:self.zoom(e,1.12)); self.canvas.bind('<Button-5>',lambda e:self.zoom(e,1/1.12))
        ttk.Label(right,textvariable=self.notice,padding=8).pack(fill=tk.X)
        self.build_inspector(outer)
        self.active_focus = None

    def refresh(self):
        prior = self.current_path
        self.tree.delete(*self.tree.get_children()); self.paths.clear(); self.tree_nodes.clear()
        initial = None
        try:
            for episode, files in discover(self.data_dir).items():
                parent = self.tree.insert('', 'end', text=episode, open=True)
                for path in files:
                    item = self.tree.insert(parent,'end',text=str(path.relative_to(self.data_dir/episode)))
                    self.paths[item] = path
                    try:
                        rows = load_edges(path)
                        for node in sorted(node_names(path,rows), key=str.casefold):
                            child = self.tree.insert(item, 'end', text=node)
                            self.tree_nodes[child] = (path, node)
                    except (OSError, ValueError):
                        logging.exception('Cannot list graph nodes: %s', path)
                    if initial is None or path == prior: initial = item
        except OSError as exc:
            messagebox.showerror('Cannot scan episodes',str(exc),parent=self)
        if initial:
            self.tree.selection_set(initial); self.tree.focus(initial)
        else:
            self.generation += 1; self.current_path=None; self.rows=[]; self.positions={}; self.graph=None; self.canvas.delete('all'); self.set_details('')
            self.notice.set(f'No episode TSV files found in {self.data_dir}')

    def select_graph(self,event=None):
        selection=self.tree.selection()
        if not selection:return
        target = self.tree_nodes.get(selection[0])
        if target:
            path, node = target
        elif selection[0] in self.paths:
            path, node = self.paths[selection[0]], None
        else:return
        self.pending_tree_node = node
        if node is not None and path == self.current_path:
            self.active_focus=None;self.hops_enabled.set(False)
            self.render()
            if node in self.deleted_nodes:self.inspect_node(node)
            return
        self.save_positions()
        self.generation += 1
        try:
            colors=load_special_nodes(self.data_dir)
            rows=load_edges(path)
            self.evidence_library.cache.clear()
            review_store=ReviewStore(path)
            reviews=review_store.records()
            verified_ids={r["edge_id"] for r in rows if review_store.verified(r,reviews)}
        except Exception as exc:
            self.current_path=None;self.rows=[];self.graph=None;self.positions={};self.canvas.delete('all');self.set_details()
            self.notice.set(f'Cannot load {path.name}')
            messagebox.showerror('Invalid graph',str(exc),parent=self);return
        self.all_positions={};self.graph=None;self.positions={}
        self.position_store=PositionStore(path);self.position_key=None
        self.current_path=path;self.rows=rows
        self.special_node_colors=colors
        self.rejected_reasons=review_store.rejections()
        self.review_store=review_store;self.verified_ids=verified_ids
        self.title(f'Katakouzina — {path.parent.name} / {path.name}')
        values=['ALL']+sorted({r['layer'] for r in rows});self.layers.configure(values=values)
        if self.layer_filter.get() not in values:self.layer_filter.set('ALL')
        self.active_focus=None;self.hops_enabled.set(False);self.whole_view=None;self.focus_text.set('');self.render()
        if node is not None and node in self.deleted_nodes:self.inspect_node(node)

    def toggle_leaves(self,event=None):
        self.hide_leaves.set(not self.hide_leaves.get())
        self.render()
        return 'break'

    def menu_hops(self):
        if self.hops_enabled.get():self.focus()
        else:self.clear_focus()

    def toggle_hops(self, event=None):
        if self.active_focus:self.clear_focus()
        else:self.focus()
        return 'break'

    def auto_arrange(self, event=None):
        self.render(force_layout=True)
        return 'break'

    def view_key(self):
        return (self.current_path,self.status_filter.get(),self.layer_filter.get(),self.hide_leaves.get(),self.show_rejected.get(),tuple(sorted(self.rejected_reasons)))

    def focus(self):
        node=self.focus_text.get().strip()
        if not node:
            self.hops_enabled.set(False)
            return
        if self.active_focus is None and self.graph is not None:
            self.whole_view=(self.view_key(),self.graph.copy(),dict(self.positions),dict(self.normalized),self.selected_node)
        self.active_focus=node;self.hops_enabled.set(True);self.render()

    def clear_focus(self):
        self.active_focus=None;self.hops_enabled.set(False)
        self.whole_view=None
        self.render()

    def coordinate_key(self):
        return json.dumps([self.status_filter.get(),self.layer_filter.get(),self.hide_leaves.get(),self.show_rejected.get(),self.active_focus],ensure_ascii=False)

    def save_positions(self):
        if self.position_save_job is not None:
            self.after_cancel(self.position_save_job);self.position_save_job=None
        if self.position_store is not None and self.position_key is not None and self.graph is not None:
            try:self.position_store.save(self.position_key,self.positions)
            except Exception as exc:
                logging.exception('Cannot save coordinates')
                self.notice.set('Cannot save node positions: '+str(exc))

    def close_app(self):
        self.save_positions()
        if self.config_root is not None:
            try:save_preferences(self.config_root,{'show_rejected_edges':self.show_rejected.get(),'hide_leaves':self.hide_leaves.get(),'graph_font_size':self.label_font.cget('size'),'start_maximized':self.state()=='zoomed'})
            except Exception as exc:
                messagebox.showerror('Cannot save preferences',str(exc),parent=self);return
        self.destroy()

    def render(self,force_layout=False):
        if self.current_path is None:return
        self.save_positions()
        self.position_key=self.coordinate_key()
        self.generation+=1;generation=self.generation
        self.deleted_nodes,self.deleted_edges=DeletionStore(self.current_path).active()
        visible_rows=[r for r in self.rows if r['edge_id'] not in self.deleted_edges and not {r['from'],r['to']}&self.deleted_nodes]
        if self.active_focus in self.deleted_nodes:self.active_focus=None;self.hops_enabled.set(False)
        try:
            base=project(visible_rows,self.status_filter.get(),self.layer_filter.get(),rejected_ids=self.rejected_reasons,show_rejected=self.show_rejected.get())
            self.nodes.configure(values=sorted(base))
            graph=project(visible_rows,self.status_filter.get(),self.layer_filter.get(),self.hide_leaves.get(),self.active_focus,rejected_ids=self.rejected_reasons,show_rejected=self.show_rejected.get())
        except ValueError as exc:
            self.graph=None; self.positions={}; self.normalized={}; self.canvas.delete('all'); self.set_details('')
            self.notice.set(str(exc)+' — choose Whole graph to reset.');return
        connected={r[k] for r in self.rows for k in ('from','to')}
        graph.add_nodes_from(node_names(self.current_path,self.rows)-connected-self.deleted_nodes)
        if self.pending_tree_node in self.deleted_nodes:self.pending_tree_node=None
        if self.pending_tree_node is not None:
            graph.add_node(self.pending_tree_node)
        if not force_layout and self.graph is not None:
            self.all_positions.update(self.positions)
            center=(sum(x for x,y in self.all_positions.values())/max(1,len(self.all_positions)),sum(y for x,y in self.all_positions.values())/max(1,len(self.all_positions)))
            for index,node in enumerate(sorted(set(graph)-set(self.all_positions))):
                # New nodes get an initial position without shifting existing nodes.
                self.all_positions[node]=(center[0]+40*(index%8),center[1]+40*(index//8))
            self.graph=graph
            self.positions={node:self.all_positions[node] for node in graph}
            self.normalized=dict(self.positions)
            self.draw()
            self.notice.set(f'{len(graph)} nodes · {graph.number_of_edges()} edges')
            return
        if not force_layout and self.position_store is not None:
            try:saved=self.position_store.load(self.position_key,graph)
            except Exception:
                logging.exception('Cannot load saved coordinates');saved=None
            if saved is not None:
                self.graph=graph;self.positions=saved;self.normalized=dict(saved)
                self.set_details();self.draw()
                self.notice.set(f'{len(graph)} nodes · {graph.number_of_edges()} edges')
                return
        self.notice.set(f'Arranging {len(graph)} nodes / {graph.number_of_edges()} edges…')
        self.graph=None;self.positions={};self.canvas.delete('all');self.set_details('')
        def worker():
            try:self.results.put((generation,graph,layout(graph),None))
            except Exception as exc:
                logging.exception('Layout failed');self.results.put((generation,None,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:
            while True:
                generation,graph,positions,error=self.results.get_nowait()
                if generation!=self.generation:continue
                if error:self.notice.set('Layout failed: '+error);continue
                self.graph=graph;self.normalized=positions;self.selected_node=None;self.fit()
                self.notice.set(f'{len(graph)} nodes · {graph.number_of_edges()} edges · {self.status_filter.get()} · {self.layer_filter.get()}'+(' · 2-hop view' if self.active_focus else ''))
        except queue.Empty:pass
        self.after(100,self.poll)

    def fit(self):
        if self.graph is None:return
        w=max(self.canvas.winfo_width(),200);h=max(self.canvas.winfo_height(),200)
        if not self.normalized:self.positions={};self.draw();return
        xs=[v[0] for v in self.normalized.values()];ys=[v[1] for v in self.normalized.values()]
        span=max(max(xs)-min(xs),max(ys)-min(ys),.1)
        scale=max(min(w-180,h-100),50)/span
        cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
        self.positions={n:((x-cx)*scale+w/2,(y-cy)*scale+h/2) for n,(x,y) in self.normalized.items()};self.draw()

    def frame_tree_node(self):
        node = self.pending_tree_node
        if node is None or node not in self.positions:return
        self.pending_tree_node = None
        self.selected_node = node;self.focus_text.set(node)
        # Frame the local neighborhood without rearranging or cropping the graph.
        neighborhood = {node}
        frontier = {node}
        for _ in range(2):
            frontier = {neighbor for current in frontier for neighbor in self.graph.neighbors(current)} - neighborhood
            neighborhood.update(frontier)
        x, y = self.positions[node]
        w=max(self.canvas.winfo_width(),200);h=max(self.canvas.winfo_height(),200)
        rx=max((abs(self.positions[n][0]-x) for n in neighborhood),default=0)
        ry=max((abs(self.positions[n][1]-y) for n in neighborhood),default=0)
        scale=min(max(w/2-120,40)/max(rx,100),max(h/2-80,40)/max(ry,100))
        self.all_positions.update(self.positions)
        self.all_positions={n:((u-x)*scale+w/2,(v-y)*scale+h/2) for n,(u,v) in self.all_positions.items()}
        self.positions={n:self.all_positions[n] for n in self.positions}
        self.normalized=dict(self.positions)
        self.inspect_node(node)

    def draw(self):
        self.frame_tree_node()
        self.all_positions.update(self.positions)
        if self.position_save_job is not None:self.after_cancel(self.position_save_job)
        self.position_save_job=self.after(500,self.save_positions)
        self.canvas.delete('all');self.items.clear()
        self.node_items={};self.edge_items={}
        if self.graph is None:return
        for a,b,attrs in self.graph.edges(data=True):
            x,y=self.positions[a];u,v=self.positions[b]
            color=edge_color(attrs['record'],self.verified_ids,self.rejected_reasons)
            item=self.canvas.create_line(x,y,u,v,fill=color,width=6 if self.selected_node in (a,b) else 4)
            self.items[item]=('edge',attrs['record'])
            self.edge_items[frozenset((a,b))]=item
        for n,(x,y) in self.positions.items():
            fill='#dc2626' if n==self.selected_node else '#2563eb'
            if self.active_focus:
                fill='#dc2626' if n==self.active_focus else '#2563eb' if self.graph.has_edge(self.active_focus,n) else '#94a3b8'
            fill=self.special_node_colors.get(n,fill)
            r=18 if n==self.selected_node else 14
            dot=self.canvas.create_oval(x-r,y-r,x+r,y+r,fill=fill,outline=FIELD,width=2.5)
            label=self.canvas.create_text(x+r+6,y,text=n,anchor='w',font=self.label_font,fill=TEXT,tags=('node-name',),state='normal' if self.show_node_names else 'hidden')
            self.items[dot]=('node',n);self.items[label]=('node',n)
            self.node_items[n]=(dot,label)
        if not self.positions:self.canvas.create_text(20,30,anchor='w',text='No nodes match these filters.',fill=TEXT,font=('Segoe UI',12))

    def press(self,event):
        self.drag_origin=(event.x,event.y);self.drag_node=None
        hit=self.canvas.find_withtag('current')
        item=self.items.get(hit[0]) if hit else None
        if not item:return
        kind,value=item
        if kind=='node':
            self.drag_node=value;self.selected_node=value;self.focus_text.set(value)
        self.open_selection(event)

    def open_selection(self,event):
        hit=self.canvas.find_withtag('current')
        item=self.items.get(hit[0]) if hit else None
        if not item:return
        kind,value=item
        if kind=='node':
            self.selected_node=value;self.focus_text.set(value);self.inspect_node(value)
        else:
            self.inspected_node=None;self.inspect_edge(value)
        self.draw()
        return 'break'

    def drag(self,event):
        if self.drag_origin is None:return
        dx=event.x-self.drag_origin[0];dy=event.y-self.drag_origin[1];self.drag_origin=(event.x,event.y)
        if self.drag_node in self.positions:
            node=self.drag_node
            x,y=self.positions[node];self.positions[node]=(x+dx,y+dy)
            self.all_positions[node]=self.positions[node]
            for item in self.node_items[node]:self.canvas.move(item,dx,dy)
            for neighbor in self.graph.neighbors(node):
                item=self.edge_items[frozenset((node,neighbor))]
                self.canvas.coords(item,*self.positions[node],*self.positions[neighbor])
        else:
            self.all_positions.update(self.positions)
            self.all_positions={n:(x+dx,y+dy) for n,(x,y) in self.all_positions.items()}
            self.positions={n:self.all_positions[n] for n in self.positions}
            self.canvas.move('all',dx,dy)
        if self.position_save_job is not None:self.after_cancel(self.position_save_job)
        self.position_save_job=self.after(500,self.save_positions)

    def change_font_size(self, delta):
        size = max(6, min(48, self.label_font.cget('size') + delta))
        self.label_font.configure(size=size)
        return 'break'

    def zoom(self,event,factor=None):
        if not self.positions:return
        factor=factor or (1.12 if event.delta>0 else 1/1.12)
        self.all_positions.update(self.positions)
        self.all_positions={n:(event.x+(x-event.x)*factor,event.y+(y-event.y)*factor) for n,(x,y) in self.all_positions.items()}
        self.positions={n:self.all_positions[n] for n in self.positions};self.draw()

    def on_callback_error(self,kind,value,traceback):
        logging.error('UI callback failed',exc_info=(kind,value,traceback))
        messagebox.showerror('Katakouzina error',str(value)+'\nDetails saved in logs/app.log.',parent=self)

    def context_menu(self,event):
        hit=self.canvas.find_withtag('current')
        value=self.items.get(hit[0]) if hit else None
        if value is None:return
        kind,target=value
        menu=tk.Menu(self,tearoff=False)
        if kind=='edge':
            choices=tk.Menu(menu,tearoff=False)
            a,b=target['from'],target['to']
            choices.add_command(label=a,command=lambda:self.apply_topology('merge',b,a))
            choices.add_command(label=b,command=lambda:self.apply_topology('merge',a,b))
            menu.add_cascade(label='Merge',menu=choices)
            menu.add_command(label='Delete edge',command=lambda:self.soft_delete('edges',target['edge_id']))
        else:
            menu.add_command(label='Delete node',command=lambda:self.soft_delete('nodes',target))
            menu.add_command(label='Split…',command=lambda:self.split_dialog(target))
            choices=tk.Menu(menu,tearoff=False)
            candidates=nearest_nodes(self.positions,target)
            existing={r['to'] if r['from']==target else r['from'] for r in self.rows if target in (r['from'],r['to'])}
            for node in candidates:
                choices.add_command(label=node,state='disabled' if node in existing else 'normal',
                                    command=lambda n=node:self.apply_topology('join',target,n))
            menu.add_cascade(label='Join',menu=choices,state='normal' if candidates else 'disabled')
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()

    def split_dialog(self,node):
        dialog=tk.Toplevel(self);dialog.title('Split '+node);dialog.transient(self)
        dialog.configure(background=FIELD)
        body=ttk.Frame(dialog,padding=16);body.pack(fill=tk.BOTH,expand=True)
        ttk.Label(body,text='New node name').pack(anchor='w')
        name=tk.StringVar();inherit=tk.BooleanVar(value=False)
        entry=ttk.Entry(body,textvariable=name,width=40);entry.pack(fill=tk.X,pady=8)
        ttk.Checkbutton(body,text='Inherit original edges',variable=inherit).pack(anchor='w')
        def submit():
            if self.apply_topology('split',node,name.get(),inherit.get()):dialog.destroy()
        ttk.Button(body,text='Split',command=submit).pack(side=tk.RIGHT,pady=12)
        ttk.Button(body,text='Cancel',command=dialog.destroy).pack(side=tk.RIGHT,padx=8,pady=12)
        dialog.bind('<Return>',lambda e:submit());dialog.bind('<Escape>',lambda e:dialog.destroy())
        dialog.grab_set();entry.focus_set()

    def apply_topology(self,action,original,name,inherit=False):
        try:
            rows=edit_topology(self.current_path,self.rows,action,original,name,inherit)
        except Exception as exc:
            messagebox.showerror('Cannot edit graph',str(exc),parent=self);return False
        name=name.strip()
        self.rows=rows
        reviews=self.review_store.records()
        self.verified_ids={r['edge_id'] for r in rows if self.review_store.verified(r,reviews)}
        self.rejected_reasons=self.review_store.rejections()
        self.all_positions.update(self.positions)
        if action=='split':
            self.hide_leaves.set(False)
            x,y=self.all_positions.get(original,(200,200));self.all_positions[name]=(x+60,y+60)
        elif action=='merge':
            self.all_positions.pop(original,None)
            self.positions.pop(original,None)
        # Rebuild just this file's node branches, without reloading the viewport.
        for item,path in self.paths.items():
            if path==self.current_path:
                for child in self.tree.get_children(item):
                    self.tree_nodes.pop(child,None);self.tree.delete(child)
                for node in sorted(node_names(path,rows),key=str.casefold):
                    child=self.tree.insert(item,'end',text=node);self.tree_nodes[child]=(path,node)
        self.active_focus=None;self.hops_enabled.set(False)
        self.selected_node=name;self.focus_text.set(name)
        self.render();self.inspect_node(name)
        return True

    def soft_delete(self,kind,key,deleted=True):
        try:DeletionStore(self.current_path).set(kind,key,deleted)
        except Exception as exc:
            messagebox.showerror('Cannot save deletion',str(exc),parent=self);return
        self.render()
        if kind=='nodes':self.inspect_node(key)
        else:
            row=next((r for r in self.rows if r['edge_id']==key),None)
            if row:self.inspect_edge(row)

    def open_arc_diagram(self):
        if self.graph is None:
            messagebox.showinfo('Arc diagram','Select a graph and wait for layout to finish.',parent=self);return
        rows=[dict(attrs['record']) for a,b,attrs in self.graph.edges(data=True)]
        try:ArcWindow(self,rows)
        except Exception as exc:messagebox.showerror('Cannot draw arc diagram',str(exc),parent=self)

    def toggle_node_names(self):
        self.show_node_names=not self.show_node_names
        self.canvas.itemconfigure('node-name',state='normal' if self.show_node_names else 'hidden')
        return 'break'
