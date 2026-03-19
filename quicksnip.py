#!/usr/bin/env python3
import gi
import sys
import os

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo
from collections import deque

VERSION = "1.0.0"
MAX_UNDO_STEPS = 20


class PaintApp:
    def __init__(self):
        self.window = Gtk.Window(title="QuickSnip")
        self.window.set_default_size(800, 600)
        self.window.connect("destroy", Gtk.main_quit)
        self.window.connect("key-press-event", self.on_key_press)
        self.window.connect("configure-event", self.on_configure)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect("draw", self.on_draw)
        self.drawing_area.connect("button-press-event", self.on_button_press)
        self.drawing_area.connect("motion-notify-event", self.on_motion)
        self.drawing_area.connect("button-release-event", self.on_button_release)
        self.drawing_area.connect("scroll-event", self.on_scroll)
        self.drawing_area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
        )

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.add(self.drawing_area)

        paste_btn = Gtk.Button(label="📋 Paste")
        paste_btn.connect("clicked", self.paste_image)

        save_btn = Gtk.Button(label="💾 Save as...")
        save_btn.connect("clicked", self.save_image)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)

        copy_btn = Gtk.Button(label="📄 Copy")
        copy_btn.connect("clicked", self.copy_image)

        clear_btn = Gtk.Button(label="🗑️ Clear")
        clear_btn.connect("clicked", self.clear_canvas)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)

        help_btn = Gtk.Button(label="❓ Help")
        help_btn.connect("clicked", self.show_help)

        note_label = Gtk.Label(label="(Draw with LMB)")

        hbox = Gtk.Box(spacing=6)
        hbox.pack_start(paste_btn, False, False, 0)
        hbox.pack_start(save_btn, False, False, 0)
        hbox.pack_start(sep1, False, False, 0)
        hbox.pack_start(copy_btn, False, False, 0)
        hbox.pack_start(clear_btn, False, False, 0)
        hbox.pack_start(sep2, False, False, 0)
        hbox.pack_start(help_btn, False, False, 0)
        hbox.pack_start(note_label, False, False, 6)

        self.toast_label = Gtk.Label()
        ctx = self.toast_label.get_style_context()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            .toast {
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
            }
        """
        )
        ctx.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.toast_label.set_halign(Gtk.Align.CENTER)
        self.toast_label.set_valign(Gtk.Align.START)
        self.toast_label.set_margin_top(10)
        self.toast_label.get_style_context().add_class("toast")
        self.toast_label.set_no_show_all(True)

        self.toast_overlay = Gtk.Overlay()

        self.toast_overlay.add_overlay(self.toast_label)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self.scrolled_window, True, True, 0)

        self.toast_overlay.add(vbox)

        self.window.add(self.toast_overlay)

        self.surface = None
        self.original_surface = None
        self.last_x = None
        self.last_y = None
        self.drawing = False
        self.zoom_level = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.undo_stack = deque(maxlen=MAX_UNDO_STEPS)

        self.window.show_all()

    def save_undo_state(self):
        if self.original_surface is None:
            return

        width = self.original_surface.get_width()
        height = self.original_surface.get_height()

        copy_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        cr = cairo.Context(copy_surface)
        cr.set_source_surface(self.original_surface, 0, 0)
        cr.paint()

        self.undo_stack.append((copy_surface, self.zoom_level))

    def undo(self):
        if len(self.undo_stack) == 0:
            self.show_toast("Nothing to undo")
            return

        self.original_surface, self.zoom_level = self.undo_stack.pop()
        self.update_zoomed_surface()
        self.show_toast("↩ Undone")

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_v and (event.state & Gdk.ModifierType.CONTROL_MASK):
            self.paste_image(None)
            return True
        elif event.keyval == Gdk.KEY_s and (
            event.state & Gdk.ModifierType.CONTROL_MASK
        ):
            self.save_image(None)
            return True
        elif event.keyval == Gdk.KEY_c and (
            event.state & Gdk.ModifierType.CONTROL_MASK
        ):
            self.copy_image(None)
            return True
        elif event.keyval == Gdk.KEY_z and (
            event.state & Gdk.ModifierType.CONTROL_MASK
        ):
            self.undo()
            return True
        elif event.keyval == Gdk.KEY_Escape:
            self.clear_canvas(None)
            return True
        return False

    def on_configure(self, widget, event):
        if self.original_surface is not None:
            self.center_image()
        return False

    def show_toast(self, message):
        self.toast_label.set_text(message)
        self.toast_label.show()
        GLib.timeout_add(2000, self.hide_toast)

    def hide_toast(self):
        self.toast_label.hide()
        return False

    def show_help(self, widget):
        dialog = Gtk.Dialog(title="Help", parent=self.window, flags=0)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        text = Gtk.Label(
            label=f"""<b>QuickSnip v{VERSION}</b>

A minimal tool for annotating screenshots.

<b>Controls:</b>
• Ctrl+V: Paste image
• Ctrl+C: Copy to clipboard
• Ctrl+S: Save as PNG
• Ctrl+Z: Undo (20 steps)
• ESC: Clear canvas
• Ctrl+scroll: Zoom

<b>GitHub:</b> github.com/yonie/quicksnip

<b>License:</b> MIT"""
        )
        text.set_use_markup(True)
        text.set_margin_start(15)
        text.set_margin_end(15)
        text.set_margin_top(15)
        text.set_margin_bottom(15)

        box = dialog.get_content_area()
        box.add(text)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def center_image(self):
        if self.surface is None:
            return

        window_width = self.scrolled_window.get_allocated_width()
        window_height = self.scrolled_window.get_allocated_height()

        img_width = self.surface.get_width()
        img_height = self.surface.get_height()

        self.offset_x = (window_width - img_width) / 2
        self.offset_y = (window_height - img_height) / 2

        if self.offset_x < 0:
            self.offset_x = 0
        if self.offset_y < 0:
            self.offset_y = 0

        self.drawing_area.queue_draw()

    def ensure_surface_size(self, width, height):
        if self.surface is None:
            return cairo.ImageSurface(cairo.Format.ARGB32, width, height)

        old_width = self.surface.get_width()
        old_height = self.surface.get_height()

        if width <= old_width and height <= old_height:
            return self.surface

        new_width = max(width, old_width)
        new_height = max(height, old_height)
        new_surface = cairo.ImageSurface(cairo.Format.ARGB32, new_width, new_height)

        cr = cairo.Context(new_surface)
        cr.set_source_surface(self.surface, 0, 0)
        cr.paint()

        return new_surface

    def fit_to_window(self):
        if self.original_surface is None:
            return

        window_width = self.scrolled_window.get_allocated_width() - 20
        window_height = self.scrolled_window.get_allocated_height() - 20

        img_width = self.original_surface.get_width()
        img_height = self.original_surface.get_height()

        scale_x = window_width / img_width
        scale_y = window_height / img_height
        self.zoom_level = min(scale_x, scale_y, 1.0)

        if self.zoom_level < 0.1:
            self.zoom_level = 0.1

        self.update_zoomed_surface()
        self.center_image()

    def update_zoomed_surface(self):
        if self.original_surface is None:
            return

        width = self.original_surface.get_width()
        height = self.original_surface.get_height()

        new_width = int(width * self.zoom_level)
        new_height = int(height * self.zoom_level)

        self.surface = cairo.ImageSurface(cairo.Format.ARGB32, new_width, new_height)

        cr = cairo.Context(self.surface)
        cr.scale(self.zoom_level, self.zoom_level)
        cr.set_source_surface(self.original_surface, 0, 0)
        cr.paint()

        self.drawing_area.set_size_request(new_width, new_height)
        self.center_image()

    def on_scroll(self, widget, event):
        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
            return False

        if self.original_surface is None:
            return False

        old_zoom = self.zoom_level

        if event.direction == Gdk.ScrollDirection.UP:
            self.zoom_level *= 1.1
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.zoom_level /= 1.1
            if self.zoom_level < 0.1:
                self.zoom_level = 0.1

        zoom_ratio = self.zoom_level / old_zoom

        self.offset_x = (self.offset_x + event.x) * zoom_ratio - event.x
        self.offset_y = (self.offset_y + event.y) * zoom_ratio - event.y

        self.update_zoomed_surface()
        return True

    def load_from_file(self, filepath):
        if not os.path.exists(filepath):
            self.show_toast(f"Could not open {os.path.basename(filepath)}")
            return False

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filepath)
        except Exception:
            self.show_toast(f"Could not open {os.path.basename(filepath)}")
            return False

        width = pixbuf.get_width()
        height = pixbuf.get_height()

        self.undo_stack.clear()

        self.original_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        cr = cairo.Context(self.original_surface)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()

        self.fit_to_window()
        return True

    def paste_image(self, widget):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        pixbuf = clipboard.wait_for_image()
        if pixbuf is None:
            self.show_toast("No image in clipboard")
            return

        width = pixbuf.get_width()
        height = pixbuf.get_height()

        self.undo_stack.clear()

        self.original_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        cr = cairo.Context(self.original_surface)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()

        self.fit_to_window()

    def on_draw(self, widget, cr):
        if self.surface is not None:
            cr.set_source_surface(self.surface, self.offset_x, self.offset_y)
            cr.paint()
        else:
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.paint()

            text = "Please paste an image..."
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.set_font_size(20)

            text_width = cr.text_extents(text).width
            text_height = cr.text_extents(text).height

            width = widget.get_allocated_width()
            height = widget.get_allocated_height()

            x = (width - text_width) / 2
            y = (height + text_height) / 2

            cr.move_to(x, y)
            cr.show_text(text)
        return False

    def on_button_press(self, widget, event):
        if event.button == 1 and self.original_surface is not None:
            self.save_undo_state()
            self.last_x = (event.x - self.offset_x) / self.zoom_level
            self.last_y = (event.y - self.offset_y) / self.zoom_level
            self.drawing = True

    def on_motion(self, widget, event):
        if not self.drawing or self.original_surface is None:
            return
        if self.last_x is None or self.last_y is None:
            return

        current_x = (event.x - self.offset_x) / self.zoom_level
        current_y = (event.y - self.offset_y) / self.zoom_level

        cr = cairo.Context(self.original_surface)
        cr.set_source_rgb(1, 0, 0)
        cr.set_line_width(3 / self.zoom_level)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(self.last_x, self.last_y)
        cr.line_to(current_x, current_y)
        cr.stroke()

        self.update_zoomed_surface()

        self.last_x = current_x
        self.last_y = current_y

    def on_button_release(self, widget, event):
        if event.button == 1:
            self.drawing = False
            self.last_x = None
            self.last_y = None

    def clear_canvas(self, widget):
        if self.original_surface is not None:
            self.save_undo_state()
        self.surface = None
        self.original_surface = None
        self.zoom_level = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.drawing_area.queue_draw()

    def save_image(self, widget):
        if self.original_surface is None:
            return

        dialog = Gtk.Dialog(title="Save as PNG", parent=self.window)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)

        file_chooser = Gtk.FileChooserWidget(action=Gtk.FileChooserAction.SAVE)
        file_chooser.set_current_name("untitled.png")
        dialog.get_content_area().pack_start(file_chooser, True, True, 0)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = file_chooser.get_filename()
            self.original_surface.write_to_png(filepath)
        dialog.destroy()

    def copy_image(self, widget):
        if self.original_surface is None:
            return

        width = self.original_surface.get_width()
        height = self.original_surface.get_height()

        stride = cairo.ImageSurface.format_stride_for_width(cairo.Format.ARGB32, width)
        new_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)

        cr = cairo.Context(new_surface)
        cr.set_source_surface(self.original_surface, 0, 0)
        cr.paint()

        new_surface.flush()

        data = new_surface.get_data()
        pixels = bytearray(data)

        for i in range(0, len(pixels), 4):
            r = pixels[i + 0]
            g = pixels[i + 1]
            b = pixels[i + 2]
            a = pixels[i + 3]
            pixels[i + 0] = b
            pixels[i + 1] = g
            pixels[i + 2] = r
            pixels[i + 3] = a

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            bytes(pixels), GdkPixbuf.Colorspace.RGB, True, 8, width, height, stride
        )

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(pixbuf)
        self.show_toast("✓ Copied to clipboard!")


if __name__ == "__main__":
    app = PaintApp()

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        GLib.idle_add(lambda: (app.load_from_file(filepath), False)[1])

    Gtk.main()
