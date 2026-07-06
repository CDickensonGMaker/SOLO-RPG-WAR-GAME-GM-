"""
Diagnostic test for Oracle display issues.
Run this and tell me what you see.
"""
import dearpygui.dearpygui as dpg

dpg.create_context()

# No theme - just raw DearPyGui
with dpg.window(label='Display Test', tag='main', width=1000, height=700):
    dpg.add_text('=== ORACLE DISPLAY TEST ===', color=(255, 255, 0))
    dpg.add_text('If you can read this, text rendering works.')
    dpg.add_separator()

    with dpg.group(horizontal=True):
        # Left panel
        with dpg.child_window(width=500, height=400, border=True):
            dpg.add_text('LEFT PANEL', color=(0, 255, 0))
            dpg.add_text('This simulates the Chat Panel area.')
            dpg.add_separator()

            with dpg.child_window(height=200, border=True, tag='chat_area'):
                dpg.add_text('[GM] Welcome, adventurer!', color=(200, 180, 140))
                dpg.add_text('[You] Hello!', color=(100, 180, 220))

            dpg.add_input_text(hint='Type here...', width=-1)
            dpg.add_button(label='Send', width=100)

        dpg.add_spacer(width=20)

        # Right panel
        with dpg.child_window(width=300, height=400, border=True):
            dpg.add_text('RIGHT PANEL', color=(0, 255, 0))
            dpg.add_text('This simulates the Session Panel.')
            dpg.add_separator()

            dpg.add_text('Scene: Dark Forest')
            dpg.add_text('Mood: Mysterious')
            dpg.add_slider_int(label='Chaos', default_value=5, min_value=1, max_value=9)

    dpg.add_separator()
    dpg.add_text('If you see TWO panels above (LEFT and RIGHT), the layout works.')
    dpg.add_text('Press ESC or close window to exit.')

dpg.create_viewport(title='Oracle Display Test', width=1100, height=800)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window('main', True)
dpg.start_dearpygui()
dpg.destroy_context()
