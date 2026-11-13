//! Pixels into terminal cells, with the half-block glyph.
//!
//! `▀` is two vertically stacked pixels — foreground paints the top one, background the bottom —
//! so a cell, which is about twice as tall as it is wide, holds two pixels that come out square.
//! It is how the 3D view in [`crate::duck`] draws the robot and how [`crate::camera`] draws a
//! frame off the camera, and both want the same four cases handled the same way, including the
//! one that is easy to get wrong: where only one pixel of a pair is lit, the other must stay the
//! terminal's own background rather than being painted black, so a drawing sits on whatever theme
//! is running.

use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::Color;

/// Paint `area`, asking `pixel` for each `(x, y)` of the `area.width × 2 * area.height` grid.
///
/// `None` is transparent — see the module doc.
pub(crate) fn blit(area: Rect, buf: &mut Buffer, pixel: impl Fn(usize, usize) -> Option<[u8; 3]>) {
    for row in 0..area.height {
        for col in 0..area.width {
            let top = pixel(col as usize, row as usize * 2);
            let bottom = pixel(col as usize, row as usize * 2 + 1);
            let Some(cell) = buf.cell_mut((area.x + col, area.y + row)) else {
                continue;
            };
            match (top, bottom) {
                (Some(t), Some(b)) => {
                    cell.set_symbol("▀").set_fg(rgb(t)).set_bg(rgb(b));
                }
                (Some(t), None) => {
                    cell.set_symbol("▀").set_fg(rgb(t));
                }
                (None, Some(b)) => {
                    cell.set_symbol("▄").set_fg(rgb(b));
                }
                (None, None) => {}
            }
        }
    }
}

fn rgb(c: [u8; 3]) -> Color {
    Color::Rgb(c[0], c[1], c[2])
}
