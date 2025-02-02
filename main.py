import copy
import os
from typing import List

import bokeh.application
from bokeh.driving import linear
from bokeh.layouts import layout
from bokeh.models import (
    Select,
    Paragraph,
    ColumnDataSource,
    TableColumn,
    DataTable,
    Button,
    Div,
)
from bokeh.models.widgets import Tabs, Panel
from bokeh.plotting import curdoc
from bokeh.plotting import figure
from bokeh.plotting.figure import Figure

import gt7communication
import gt7helper
from gt7helper import (
    get_speed_peaks_and_valleys,
    load_laps_from_pickle,
    save_laps_to_pickle,
    list_lap_files_from_path,
    calculate_time_diff_by_distance,
)
from gt7lap import Lap


def get_throttle_velocity_diagram_for_reference_lap_and_last_lap(
    width: int,
) -> tuple[Figure, Figure, Figure, Figure, Figure, list[ColumnDataSource]]:
    tooltips = [
        ("index", "$index"),
        ("value", "$y"),
        ("Speed", "@speed{0} kph"),
        ("Throttle", "@throttle%"),
        ("Brake", "@brake%"),
        ("Coast", "@coast%"),
        ("Distance", "@distance{0} m"),
    ]

    tooltips_timedelta = [
        ("index", "$index"),
        ("timedelta", "@timedelta{0} ms"),
        ("reference", "@reference{0} ms"),
        ("comparison", "@comparison{0} ms"),
    ]
    colors = ["blue", "magenta", "green"]
    legends = ["Last Lap", "Reference Lap", "Median Lap"]

    f_speed = figure(
        title="Last, Reference, Median",
        y_axis_label="Speed",
        width=width,
        height=250,
        tooltips=tooltips,
        active_drag="box_zoom",
    )

    f_time_diff = figure(
        title="Time Diff - Last, Reference",
        x_range=f_speed.x_range,
        y_axis_label="Time / Diff",
        width=width,
        height=int(f_speed.height / 2),
        tooltips=tooltips_timedelta,
        active_drag="box_zoom",
    )

    f_throttle = figure(
        x_range=f_speed.x_range,
        y_axis_label="Throttle",
        width=width,
        height=int(f_speed.height / 2),
        tooltips=tooltips,
        active_drag="box_zoom",
    )
    f_braking = figure(
        x_range=f_speed.x_range,
        y_axis_label="Braking",
        width=width,
        height=int(f_speed.height / 2),
        tooltips=tooltips,
        active_drag="box_zoom",
    )

    f_coasting = figure(
        x_range=f_speed.x_range,
        y_axis_label="Coasting",
        width=width,
        height=int(f_speed.height / 2),
        tooltips=tooltips,
        active_drag="box_zoom",
    )

    f_speed.toolbar.autohide = True

    span_zero_time_diff = bokeh.models.Span(
        location=0,
        dimension="width",
        line_color="black",
        line_dash="dashed",
        line_width=1,
    )
    f_time_diff.add_layout(span_zero_time_diff)

    f_time_diff.toolbar.autohide = True

    f_throttle.xaxis.visible = False
    f_throttle.toolbar.autohide = True

    f_braking.xaxis.visible = False
    f_braking.toolbar.autohide = True

    f_coasting.xaxis.visible = False
    f_coasting.toolbar.autohide = True

    sources = []

    # Set empty data for avoiding warnings about missing columns
    dummy_data = gt7helper.get_data_from_lap(Lap(), distance_mode=True)

    time_diff_source = ColumnDataSource(data={})
    f_time_diff.line(
        x="distance",
        y="timedelta",
        source=time_diff_source,
        line_width=1,
        color="blue",
        line_alpha=1,
    )
    sources.append(time_diff_source)

    for color, legend in zip(colors, legends):
        source = ColumnDataSource(data=dummy_data)
        sources.append(source)

        f_speed.line(
            x="distance",
            y="speed",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
        )
        f_throttle.line(
            x="distance",
            y="throttle",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
        )
        f_braking.line(
            x="distance",
            y="brake",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
        )
        f_coasting.line(
            x="distance",
            y="coast",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
        )

    f_speed.legend.click_policy = "hide"
    f_throttle.legend.click_policy = f_speed.legend.click_policy
    f_braking.legend.click_policy = f_speed.legend.click_policy
    f_coasting.legend.click_policy = f_speed.legend.click_policy

    return f_time_diff, f_speed, f_throttle, f_braking, f_coasting, sources


def update_connection_info():
    div_connection_info.text = ""
    if app.gt7comm.is_connected():
        div_connection_info.text += "<p title='Connected'>🟢</p>"
    else:
        div_connection_info.text += "<p title='Disconnected'>🔴</p>"


def update_reference_lap_select(laps):
    reference_lap_select.options = [
        tuple(("-1", "Best Lap"))
    ] + gt7helper.bokeh_tuple_for_list_of_laps(laps)


@linear()
def update_fuel_map(step):
    global g_stored_fuel_map

    if len(app.gt7comm.laps) == 0:
        div_fuel_map.text = ""
        return

    last_lap = app.gt7comm.laps[0]

    if last_lap == g_stored_fuel_map:
        return
    else:
        g_stored_fuel_map = last_lap

    # TODO Add real live data during a lap
    fuel_maps = gt7helper.get_fuel_on_consumption_by_relative_fuel_levels(last_lap)

    table = (
        "<table><tr>"
        "<th title='The fuel level relative to the current one'>Fuel Lvl.</th>"
        "<th title='Fuel consumed'>Fuel Cons.</th>"
        "<th title='Laps remaining with this setting'>Laps Rem.</th>"
        "<th title='Time remaining with this setting' >Time Rem.</th>"
        "<th title='Time Diff to last lap with this setting'>Time Diff</th></tr>"
    )
    for fuel_map in fuel_maps:
        table += (
            "<tr id='fuel_map_row_%d'>"
            "<td style='text-align:center'>%d</td>"
            "<td style='text-align:center'>%d</td>"
            "<td style='text-align:center'>%.1f</td>"
            "<td style='text-align:center'>%s</td>"
            "<td style='text-align:center'>%s</td>"
            "</tr>"
            % (
                fuel_map.mixture_setting,
                fuel_map.mixture_setting,
                fuel_map.fuel_consumed_per_lap,
                fuel_map.laps_remaining_on_current_fuel,
                gt7helper.seconds_to_lap_time(
                    fuel_map.time_remaining_on_current_fuel / 1000
                ),
                gt7helper.seconds_to_lap_time(fuel_map.lap_time_diff / 1000),
            )
        )
    table += "</table>"
    table += "<p>Fuel Remaining: <b>%d</b></p>" % last_lap.fuel_at_end
    div_fuel_map.text = table


@linear()
def update_lap_change(step):
    # time, x, y, z = from_csv(reader).next()
    global g_laps_stored
    global g_session_stored
    global g_connection_status_stored
    global g_telemetry_update_needed
    global g_reference_lap_selected

    laps = app.gt7comm.get_laps()

    if app.gt7comm.session != g_session_stored:
        update_tuning_info()
        g_session_stored = copy.copy(app.gt7comm.session)

    if app.gt7comm.is_connected() != g_connection_status_stored:
        update_connection_info()
        g_connection_status_stored = copy.copy(app.gt7comm.is_connected())

    # This saves on cpu time, 99.9% of the time this is true
    if laps == g_laps_stored and not g_telemetry_update_needed:
        return

    if len(laps) > 0:

        last_lap = laps[0]
        update_speed_peak_and_valley_diagram(div_last_lap, last_lap, "Last Lap")

        if len(laps) > 1:
            reference_lap = gt7helper.get_last_reference_median_lap(
                laps, reference_lap_selected=g_reference_lap_selected
            )[1]
            if reference_lap:
                update_speed_peak_and_valley_diagram(
                    div_reference_lap, reference_lap, "Reference Lap"
                )

    update_time_table(laps)
    update_reference_lap_select(laps)
    update_speed_velocity_graph(laps)

    g_laps_stored = laps.copy()
    g_telemetry_update_needed = False


def update_speed_velocity_graph(laps: List[Lap]):
    last_lap, reference_lap, median_lap = gt7helper.get_last_reference_median_lap(
        laps, reference_lap_selected=g_reference_lap_selected
    )

    last_lap_data = gt7helper.get_data_from_lap(last_lap, distance_mode=True)
    reference_lap_data = gt7helper.get_data_from_lap(reference_lap, distance_mode=True)

    if reference_lap and len(reference_lap.data_speed) > 0:
        data_sources[0].data = calculate_time_diff_by_distance(reference_lap, last_lap)

    data_sources[1].data = last_lap_data
    data_sources[2].data = reference_lap_data
    data_sources[3].data = gt7helper.get_data_from_lap(median_lap, distance_mode=True)

    last_lap_race_line.data_source.data = last_lap_data
    reference_lap_race_line.data_source.data = reference_lap_data

    s_race_line.legend.visible = False
    s_race_line.axis.visible = False

    # Update breakpoints
    # Adding Brake Points is slow when rendering, this is on Bokehs side about 3s
    brake_points_enabled = os.environ.get("GT7_ADD_BRAKEPOINTS") == "true"

    if brake_points_enabled and len(last_lap.data_braking) > 0:
        update_break_points(last_lap, s_race_line, "blue")

    if brake_points_enabled and len(reference_lap.data_braking) > 0:
        update_break_points(reference_lap, s_race_line, "magenta")


def update_break_points(lap: Lap, race_line: Figure, color: str):
    brake_points_x, brake_points_y = gt7helper.get_brake_points(lap)

    for i, _ in enumerate(brake_points_x):
        race_line.scatter(
            brake_points_x[i],
            brake_points_y[i],
            marker="circle",
            size=10,
            fill_color=color,
        )


def update_time_table(laps: List[Lap]):
    print("Adding %d laps to table" % len(laps))
    t_lap_times.source.data = ColumnDataSource.from_df(
        gt7helper.pd_data_frame_from_lap(
            laps, best_lap_time=app.gt7comm.session.best_lap
        )
    )
    t_lap_times.trigger("source", t_lap_times.source, t_lap_times.source)


def reset_button_handler(event):
    print("reset button clicked")
    div_reference_lap.text = ""
    div_last_lap.text = ""
    app.gt7comm.reset()


def log_lap_button_handler(event):
    app.gt7comm.finish_lap(manual=True)
    print("Added a lap manually to the list of laps: %s" % app.gt7comm.laps[0])


def save_button_handler(event):
    path = save_laps_to_pickle(app.gt7comm.laps)
    print("Saved %d laps as %s" % (len(app.gt7comm.laps), path))


def load_laps_handler(attr, old, new):
    print("Loading %s" % new)
    app.gt7comm.load_laps(load_laps_from_pickle(new), replace_other_laps=True)


def load_reference_lap_handler(attr, old, new):
    global g_reference_lap_selected
    global reference_lap_select
    global g_telemetry_update_needed

    if int(new) == -1:
        # Set no reference lap
        g_reference_lap_selected = None
    else:
        g_reference_lap_selected = g_laps_stored[int(new)]
        print("Loading %s as reference" % g_laps_stored[int(new)].format())

    g_telemetry_update_needed = True
    update_lap_change()


def update_speed_peak_and_valley_diagram(div, lap, title):
    table = """<table>"""

    (
        peak_speed_data_x,
        peak_speed_data_y,
        valley_speed_data_x,
        valley_speed_data_y,
    ) = get_speed_peaks_and_valleys(lap)

    table += '<tr><th colspan="3">%s - %s</th></tr>' % (title, lap.title)

    table = table + "<tr><th>#</th><th>Peak</th><th>Position</th></tr>"
    for i, dx in enumerate(peak_speed_data_x):
        table = table + "<tr><td>%d.</td><td>%d kph</td><td>%d</td></tr>" % (
            i + 1,
            peak_speed_data_x[i],
            peak_speed_data_y[i],
        )

    table = table + "<tr><th>#</th><th>Valley</th><th>Position</th></tr>"
    for i, dx in enumerate(valley_speed_data_x):
        table = table + "<tr><td>%d.</td><td>%d kph</td><td>%d</td></tr>" % (
            i + 1,
            valley_speed_data_x[i],
            valley_speed_data_y[i],
        )

    table = table + """</table>"""
    div.text = table


def update_tuning_info():
    div_tuning_info.text = """<p>Max Speed: <b>%d</b> kph</p>
    <p>Min Body Height: <b>%d</b> mm</p>""" % (
        app.gt7comm.session.max_speed,
        app.gt7comm.session.min_body_height,
    )

app = bokeh.application.Application

# Share the gt7comm connection between sessions by storing them as an application attribute
if not hasattr(app, "gt7comm"):
    playstation_ip = os.environ.get("GT7_PLAYSTATION_IP")
    load_laps_path = os.environ.get("GT7_LOAD_LAPS_PATH")

    if not playstation_ip:
        raise Exception("No IP set in env var GT7_PLAYSTATION_IP")

    app.gt7comm = gt7communication.GT7Communication(playstation_ip)

    if load_laps_path:
        app.gt7comm.load_laps(
            load_laps_from_pickle(load_laps_path), replace_other_laps=True
        )

    app.gt7comm.start()
else:
    # Reuse existing thread
    if not app.gt7comm.is_connected():
        print("Restarting gt7communcation")
        app.gt7comm.restart()
    else:
        # Existing thread has connection, proceed
        pass

source = ColumnDataSource(
    gt7helper.pd_data_frame_from_lap([], best_lap_time=app.gt7comm.session.best_lap)
)

g_laps_stored = []
g_session_stored = None
g_connection_status_stored = None
g_reference_lap_selected = None
g_stored_fuel_map = None
g_telemetry_update_needed = False

stored_lap_files = gt7helper.bokeh_tuple_for_list_of_lapfiles(
    list_lap_files_from_path("data")
)

columns = [
    TableColumn(field="number", title="#"),
    TableColumn(field="time", title="Time"),
    TableColumn(field="diff", title="Diff"),
    TableColumn(field="fuelconsumed", title="Fuel Consumed"),
    TableColumn(field="fullthrottle", title="Full Throttle"),
    TableColumn(field="fullbreak", title="Full Break"),
    TableColumn(field="nothrottle", title="No Throttle"),
    TableColumn(field="tyrespinning", title="Tire Spin"),
]

(
    f_time_diff,
    f_speed,
    f_throttle,
    f_braking,
    f_coasting,
    data_sources,
) = get_throttle_velocity_diagram_for_reference_lap_and_last_lap(width=1000)

t_lap_times = DataTable(
    source=source, columns=columns, index_position=None, css_classes=["lap_times_table"]
)
t_lap_times.autosize_mode = "fit_columns"
# t_lap_times.width = 1000
t_lap_times.min_height = 20
t_lap_times.min_width = 630

# Race line

race_line_tooltips = [("index", "$index"), ("Breakpoint", "")]
dummy_data = gt7helper.get_data_from_lap(Lap(), distance_mode=True)
race_line_width = 250
speed_diagram_width = 1200
total_width = race_line_width + speed_diagram_width
s_race_line = figure(
    title="Race Line",
    x_axis_label="z",
    y_axis_label="x",
    match_aspect=True,
    width=race_line_width,
    height=race_line_width,
    active_drag="box_zoom",
    tooltips=race_line_tooltips,
)
s_race_line.toolbar.autohide = True

last_lap_race_line = s_race_line.line(
    x="raceline_z", y="raceline_x", legend_label="Last Lap", line_width=1, color="blue"
)
reference_lap_race_line = s_race_line.line(
    x="raceline_z",
    y="raceline_x",
    legend_label="Reference Lap",
    line_width=1,
    color="magenta",
)

select_title = Paragraph(text="Load Laps:", align="center")
select = Select(value="laps", options=stored_lap_files)
select.on_change("value", load_laps_handler)

reference_lap_select = Select(value="laps")
reference_lap_select.on_change("value", load_reference_lap_handler)

manual_log_button = Button(label="Log Lap Now")
manual_log_button.on_click(log_lap_button_handler)

reset_button = Button(label="Save Laps")
reset_button.on_click(save_button_handler)

save_button = Button(label="Reset Laps")
save_button.on_click(reset_button_handler)

div_tuning_info = Div(width=200, height=100)

div_last_lap = Div(width=200, height=125)
div_reference_lap = Div(width=200, height=125)
div_connection_info = Div(width=30, height=30)

div_fuel_map = Div(width=200, height=125, css_classes=["fuel_map"])

l1 = layout(
    children=[
        [div_connection_info],
        [f_time_diff, layout(children=[manual_log_button, reference_lap_select])],
        [f_speed, s_race_line],
        [f_throttle, [[div_last_lap, div_reference_lap]]],
        [f_braking],
        [f_coasting],
        [t_lap_times, div_fuel_map],
        [div_tuning_info],
        [reset_button, save_button, select_title, select],
    ]
)

l2 = layout(
    [[reset_button, save_button], [t_lap_times], [div_fuel_map]],
    sizing_mode="stretch_width",
)

tab1 = Panel(child=l1, title="Get Faster")
tab2 = Panel(child=l2, title="Race")
tabs = Tabs(tabs=[tab1, tab2])

curdoc().add_root(tabs)
curdoc().title = "GT7 Dashboard"

# This will only trigger once per lap, but we check every second if anything happened
curdoc().add_periodic_callback(update_lap_change, 1000)
curdoc().add_periodic_callback(update_fuel_map, 5000)
