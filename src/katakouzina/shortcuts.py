"""Windows physical-key shortcuts, before focused-widget text bindings."""
import ctypes

SCAN_ACTIONS={0x31:'names',0x23:'hops',0x26:'leaves',0x24:'rejected',0x13:'arrange',0x14:'arrange',0x0d:'larger',0x4e:'larger',0x0c:'smaller',0x4a:'smaller'}

def action_for_scan(scan, state):
    # Windows Tk uses 0x8 for Num Lock, not Alt. Allow lock keys and Shift.
    # Exclude Alt/AltGr using the Windows-specific Alt mask.
    if not state & 0x4 or state & 0x20000:return None
    return SCAN_ACTIONS.get(scan)

def install(root):
    tag='KatakouzinaShortcuts'
    actions={'names':root.toggle_node_names,'hops':root.toggle_hops,'leaves':root.toggle_leaves,'rejected':root.toggle_rejected_visibility,'arrange':root.auto_arrange,'larger':lambda:root.change_font_size(1),'smaller':lambda:root.change_font_size(-1)}
    def dispatch(event):
        if event.widget.winfo_toplevel() is not root:return
        scan=ctypes.windll.user32.MapVirtualKeyW(event.keycode,0)
        action=action_for_scan(scan,event.state)
        if action:
            actions[action]()
            return 'break'
    root.bind_class(tag,'<KeyPress>',dispatch)
    def attach(widget):
        tags=widget.bindtags()
        if tag not in tags:widget.bindtags((tag,)+tags)
        for child in widget.winfo_children():attach(child)
    attach(root)
    root.bind_all('<Map>',lambda event:attach(event.widget),add='+')
