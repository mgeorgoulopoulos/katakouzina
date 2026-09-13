"""Readable node, edge, and subtitle inspector without tabs."""
import tkinter as tk
from tkinter import ttk, messagebox
from .evidence import references
from .theme import BG, TEXT

class Inspector:
    def build_inspector(self, outer):
        style=ttk.Style(self)
        style.configure('Accepted.TFrame',background='#243b30')
        style.configure('Rejected.TFrame',background='#402b30')
        style.configure('Inspector.TButton',font=('Segoe UI',12))
        style.configure('Inspector.TCheckbutton',font=('Segoe UI',12))
        panel=ttk.Frame(outer,width=480,padding=8);outer.add(panel,weight=0)
        self.inspector_title=tk.StringVar(value='Inspector')
        ttk.Label(panel,textvariable=self.inspector_title,font=('Segoe UI',16,'bold'),wraplength=440).pack(anchor='w',pady=8)
        canvas=tk.Canvas(panel,width=460,highlightthickness=0)
        scroll=ttk.Scrollbar(panel,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set);scroll.pack(side=tk.RIGHT,fill=tk.Y);canvas.pack(fill=tk.BOTH,expand=True)
        self.inspector_body=ttk.Frame(canvas)
        window=canvas.create_window(0,0,window=self.inspector_body,anchor='nw')
        self.inspector_body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.inspector_canvas=canvas
        self.connection_rows={};self.inspected_edge=None;self.inspected_node=None
        self.human_rejected=tk.BooleanVar()
        self.human_verified=tk.BooleanVar();self.review_notice=tk.StringVar()
        self.reason_drafts={}
        self.why_editor=None
        self.set_details()

    def clear_inspector(self):
        if self.why_editor is not None and self.why_editor.winfo_exists() and self.inspected_edge and not self.human_rejected.get():
            self.reason_drafts[(str(self.current_path),self.inspected_edge['edge_id'])]=self.why_editor.get('1.0','end-1c')
        self.why_editor=None
        for widget in self.inspector_body.winfo_children():widget.destroy()
        self.inspector_canvas.yview_moveto(0)

    def paragraph(self, text, bold=False, parent=None):
        parent=parent or self.inspector_body
        label=ttk.Label(parent,text=text,wraplength=420,justify='left',font=('Segoe UI',12,'bold' if bold else 'normal'))
        label.pack(fill=tk.X,anchor='w',pady=5,padx=6)
        label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width-12)))
        return label

    def set_details(self, text=''):
        self.clear_inspector();self.inspected_edge=None;self.inspected_node=None;self.connection_rows.clear()
        self.inspector_title.set('Inspector')

    def inspect_node(self,node):
        self.clear_inspector();self.inspected_edge=None;self.inspected_node=node;self.connection_rows.clear()
        self.inspector_title.set(node)
        if node in self.deleted_nodes:
            ttk.Button(self.inspector_body,text='Restore deleted node',command=lambda:self.soft_delete('nodes',node,False)).pack(anchor='w')
        if self.review_store is not None:
            self.rejected_reasons=self.review_store.rejections()
            reviews=self.review_store.records()
            self.verified_ids={r['edge_id'] for r in self.rows if self.review_store.verified(r,reviews)}
        records=[r for r in self.rows if node in (r['from'],r['to'])]
        records.sort(key=lambda r:(0 if r['edge_id'] in self.rejected_reasons else 1 if r['edge_id'] in self.verified_ids else 2,
                                   (r['to'] if r['from']==node else r['from']).casefold()))
        self.paragraph(f'{len(records)} connections')
        for row in records:
            other=row['to'] if row['from']==node else row['from']
            card=tk.Frame(self.inspector_body,background=BG,padx=8,pady=8,relief='flat',borderwidth=0,highlightthickness=1,highlightbackground='#414854');card.pack(fill=tk.X,pady=4)
            title=self.paragraph(node+' ↔ '+other,True,card)
            status=self.paragraph(('AI rejection' if row['status']=='REJECTED' else self.readable(row['status']))+' · '+('Verified by human' if row['edge_id'] in self.verified_ids else 'Not yet human-verified'),parent=card)
            why=self.rejected_reasons.get(row['edge_id'],self.edge_reason(row))
            if row['status']=='REJECTED':why='AI rejection\n'+why
            reason=self.paragraph(why,parent=card)
            if row['edge_id'] in self.deleted_edges or {row['from'],row['to']}&self.deleted_nodes:
                status.configure(text='Deleted' if row['edge_id'] in self.deleted_edges else 'Hidden: endpoint deleted')
                for label in (title,status,reason):label.configure(foreground='#929baa')
            elif row['edge_id'] in self.rejected_reasons:
                status.configure(text='Rejected by human')
                card.configure(background='#402b30')
                for label in (title,status,reason):label.configure(background='#402b30',foreground=TEXT)
            elif row['edge_id'] in self.verified_ids:
                card.configure(background='#243b30')
                for label in (title,status,reason):label.configure(background='#243b30',foreground=TEXT)
            for widget in (card,title,status,reason):widget.bind('<Double-Button-1>',lambda e,r=row:self.inspect_edge(r))
            self.connection_rows[row['edge_id']]=row

    def edge_reason(self,row):
        return self.review_store.reason(row) if self.review_store else row.get('reason','')

    @staticmethod
    def readable(value):
        return value.replace('_',' ').capitalize()

    def inspect_edge(self,row):
        self.clear_inspector();self.inspected_edge=row
        self.inspector_title.set(row['from']+' ↔ '+row['to'])
        if row['edge_id'] in self.deleted_edges:
            ttk.Button(self.inspector_body,text='Restore deleted edge',command=lambda:self.soft_delete('edges',row['edge_id'],False)).pack(anchor='w')
        if self.inspected_node:
            ttk.Button(self.inspector_body,style='Inspector.TButton',text='← Back to '+self.inspected_node,command=lambda:self.inspect_node(self.inspected_node)).pack(anchor='w',pady=5)
        self.human_verified.set(row['edge_id'] in self.verified_ids)
        controls=ttk.Frame(self.inspector_body);controls.pack(fill=tk.X)
        self.verify_box=ttk.Checkbutton(controls,style='Inspector.TCheckbutton',text='Accepted by human',variable=self.human_verified,command=self.toggle_verified)
        self.verify_box.pack(side=tk.LEFT,pady=8)
        self.human_rejected.set(row['edge_id'] in self.rejected_reasons)
        ttk.Checkbutton(controls,style='Inspector.TCheckbutton',text='Rejected by human',variable=self.human_rejected,command=self.toggle_rejected).pack(side=tk.LEFT,padx=8)
        self.verify_box.configure(state='disabled' if self.human_rejected.get() else 'normal')
        self.review_notice.set('Review needs rechecking: the edge changed.' if self.review_store and self.review_store.stale(row) else '')
        ttk.Label(self.inspector_body,textvariable=self.review_notice,wraplength=420).pack(anchor='w')
        self.why_heading=self.paragraph('Why',True)
        if row['status']=='REJECTED':self.paragraph('AI rejection')
        self.why_editor=tk.Text(self.inspector_body,height=5,width=35,wrap='word',font=('Segoe UI',12),undo=True)
        self.why_editor.pack(fill=tk.X,pady=5)
        draft=self.reason_drafts.get((str(self.current_path),row['edge_id']),self.edge_reason(row))
        self.why_editor.insert('1.0',self.rejected_reasons.get(row['edge_id'],draft))
        ttk.Button(self.inspector_body,style='Inspector.TButton',text='Save why',command=self.save_why).pack(anchor='e')
        self.paragraph('Evidence from the episode',True)
        self.evidence_cards=[]
        excerpts=references(row)
        for ref in excerpts:
            kind,text=self.evidence_library.preview(ref)
            card=ttk.Frame(self.inspector_body,padding=8,relief='groove');card.pack(fill=tk.X,pady=4)
            stamp=self.paragraph(ref['start']+' – '+ref['end'],True,card)
            widgets=[card,stamp]
            if text:
                widgets.append(self.paragraph(text,parent=card))
            for widget in widgets:
                widget.configure(cursor='hand2');widget.bind('<Button-1>',lambda e,r=ref:self.open_evidence(r))
            self.evidence_cards.append((ref,kind,text))
        if not excerpts:self.paragraph('No subtitle passage is attached to this connection.')
        self.paragraph('Evidence reader',True)
        self.dialogue_text=tk.Text(self.inspector_body,height=12,width=35,wrap='word',font=('Segoe UI',12),state='disabled')
        self.dialogue_text.pack(fill=tk.X,pady=5)
        self.dialogue_text.tag_configure('selected',font=('Segoe UI',12,'bold'))
        if excerpts:self.open_evidence(excerpts[0])
        self.paragraph('About this connection',True)
        self.paragraph('Assessment: '+self.readable(row['status'])+'\nConnection type: '+self.readable(row['relation'])+'\nCategory: '+self.readable(row['layer']))
        self.paragraph('Supporting references',True)
        refs=row.get('external_sources','')
        self.paragraph(refs or 'No external references.')

    def open_evidence(self,ref):
        self.dialogue_entries=self.evidence_library.resolve(ref,context=True)
        self.dialogue_text.configure(state='normal');self.dialogue_text.delete('1.0','end')
        for entry in self.dialogue_entries:
            self.dialogue_text.insert('end',entry['start']+' – '+entry['end']+'\n'+entry['text']+'\n\n','selected' if entry.get('selected') else ())
        if not self.dialogue_entries:self.dialogue_text.insert('end',ref['episode']+' · '+ref['start']+' – '+ref['end'])
        self.dialogue_text.configure(state='disabled');self.dialogue_text.yview_moveto(0)

    def save_why(self):
        row=self.inspected_edge
        value=self.why_editor.get('1.0','end-1c')
        if self.human_rejected.get():
            try:self.review_store.set_rejected(row,value)
            except Exception as exc:
                messagebox.showerror('Cannot reject edge',str(exc),parent=self);return
            self.rejected_reasons[row['edge_id']]=value
            self.verified_ids.discard(row['edge_id'])
            self.refresh_review_graph(row)
            return
        try:
            self.review_store.save(row,value)
        except Exception as exc:
            messagebox.showerror('Cannot save explanation',str(exc),parent=self);return
        self.verified_ids.discard(row['edge_id']);self.human_verified.set(False)
        self.reason_drafts.pop((str(self.current_path),row['edge_id']),None)
        self.review_notice.set('Explanation saved.')
        self.draw()

    def toggle_verified(self):
        row=self.inspected_edge
        if row is None:return
        value=self.human_verified.get()
        try:self.review_store.set_verified(row,value)
        except Exception as exc:
            self.human_verified.set(row['edge_id'] in self.verified_ids)
            self.review_notice.set('Save failed; review state was not changed.')
            messagebox.showerror('Cannot save human review',str(exc),parent=self);return
        if value:self.verified_ids.add(row['edge_id'])
        else:self.verified_ids.discard(row['edge_id'])
        self.review_notice.set('Human verification saved.' if value else 'Human verification removed.')
        self.draw()

    def refresh_review_graph(self,row):
        node=self.inspected_node
        self.render()
        self.inspected_node=node
        self.inspect_edge(row)

    def toggle_rejected(self):
        row=self.inspected_edge
        if self.human_rejected.get():
            reason=''
            try:self.review_store.set_rejected(row,reason)
            except Exception as exc:
                self.human_rejected.set(False)
                messagebox.showerror('Cannot reject edge',str(exc),parent=self);return
            self.rejected_reasons[row['edge_id']]=reason
            self.verified_ids.discard(row['edge_id'])
            self.refresh_review_graph(row)
        else:
            if row['edge_id'] in self.rejected_reasons:
                try:self.review_store.set_rejected(row,None)
                except Exception as exc:
                    self.human_rejected.set(True)
                    messagebox.showerror('Cannot restore edge',str(exc),parent=self);return
                self.rejected_reasons.pop(row['edge_id'])
            self.why_editor.delete('1.0','end');self.why_editor.insert('1.0',self.edge_reason(row))
            self.refresh_review_graph(row)
