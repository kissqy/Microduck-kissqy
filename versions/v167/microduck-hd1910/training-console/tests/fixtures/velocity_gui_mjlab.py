# Upstream UniformVelocityCommand.create_gui snapshot from the existing mjlab source audit.
# Used to reproduce the actual small-limit slider assertion without GPU simulation.
from __future__ import annotations
def create_gui(self, name: str, server: viser.ViserServer, get_env_idx: Callable[[], int], on_change: Callable[[], None] | None=None, request_action: Callable[[str, Any], None] | None=None) -> None:
    """Create velocity joystick sliders in the Viser viewer."""
    from viser import Icon
    ranges = self.cfg.ranges
    axes = [('lin_vel_x', ranges.lin_vel_x[1]), ('lin_vel_y', ranges.lin_vel_y[1]), ('ang_vel_z', ranges.ang_vel_z[1])]
    sliders: list = []
    with server.gui.add_folder(name.capitalize()):
        enabled = server.gui.add_checkbox('Enable', initial_value=False)
        for label, max_val in axes:
            max_input = server.gui.add_slider(f'Max {label}', initial_value=max_val, step=0.1, min=0.1, max=10.0)
            slider = server.gui.add_slider(label, min=-max_val, max=max_val, step=0.05, initial_value=0.0)

            @max_input.on_update
            def _(_ev, _s=slider, _m=max_input) -> None:
                _s.min = -_m.value
                _s.max = _m.value
            sliders.append(slider)
        zero_btn = server.gui.add_button('Zero', icon=Icon.SQUARE_X)

        @zero_btn.on_click
        def _(_) -> None:
            for s in sliders:
                s.value = 0.0
    self._joystick_enabled = enabled
    self._joystick_sliders = sliders
    self._joystick_get_env_idx = get_env_idx
