from tkinter import ttk

BG='#20242b'
FIELD='#15191f'
TEXT='#e5e7eb'
BLUE='#3053fd'
GREEN='#25ef40'
RED='#fc3939'

def apply_dark(root):
    root.configure(background=BG)
    for pattern,value in {'*Text.background':FIELD,'*Text.foreground':TEXT,'*Text.insertBackground':TEXT,'*Text.selectBackground':'#315a85','*Canvas.background':BG,'*Listbox.background':FIELD,'*Listbox.foreground':TEXT,'*Listbox.selectBackground':'#315a85','*Menu.background':BG,'*Menu.foreground':TEXT,'*Menu.activeBackground':'#315a85','*Menu.activeForeground':'#ffffff'}.items():root.option_add(pattern,value)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',background=BG,foreground=TEXT,fieldbackground=FIELD,bordercolor='#414854',lightcolor=BG,darkcolor=BG,arrowcolor=TEXT)
    for name in ('TButton','TCheckbutton','TCombobox','Treeview','TScrollbar'):
        style.map(name,background=[('selected','#315a85'),('active','#343c48'),('disabled',BG)],foreground=[('disabled','#929baa'),('selected',TEXT)],fieldbackground=[('readonly',FIELD)],selectbackground=[('!disabled','#315a85')])
    style.configure('Treeview',background=FIELD,fieldbackground=FIELD,foreground=TEXT)
    style.configure('Treeview.Heading',background=BG,foreground=TEXT)
    style.configure('TCheckbutton',indicatorbackground=FIELD,indicatorforeground=TEXT)

def edge_color(row,accepted,rejected):
    if row.get('edge_id') in rejected:return RED
    if row.get('edge_id') in accepted:return GREEN
    return BLUE
