"""Gantt presentation of planned PEIMS activity windows and reported progress.

No actual work dates, approved revised baselines, remaining-duration forecasts,
resource loading, or critical-path dates are inferred from completion percentages.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from visuals import BLUE, GOLD, GREY, GRID, RED, TEAL, _style

GANTT_REQUIRED = (
    'activity_id', 'wbs', 'activity', 'owner', 'start_date', 'finish_date',
    'actual_pct', 'planned_pct', 'variance_pp',
)
STATUS_COLORS = {
    'Completed': TEAL,
    'Behind baseline': RED,
    'Past finish date': RED,
    'In progress': BLUE,
    'Not started': GOLD,
}


def gantt_rows(activities: pd.DataFrame, snapshot: pd.Timestamp, *,
               focus: bool = False, limit: int = 6) -> pd.DataFrame:
    """Project-scoped activity chart rows, with no fabricated actual dates."""
    missing = set(GANTT_REQUIRED) - set(activities.columns)
    if missing:
        raise ValueError('Gantt is missing activity fields: ' + ', '.join(sorted(missing)))
    if activities.empty:
        return activities.assign(gantt_status=pd.Series(dtype='string'),
                                 gantt_label=pd.Series(dtype='string'))
    df = activities.copy().reset_index(drop=True)
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['finish_date'] = pd.to_datetime(df['finish_date'])
    if df[['start_date', 'finish_date']].isna().any().any() or (df['finish_date'] < df['start_date']).any():
        raise ValueError('Gantt requires valid activity date windows')
    if df['activity_id'].astype(str).duplicated().any():
        raise ValueError('Gantt requires unique activity IDs')
    df['actual_pct'] = pd.to_numeric(df['actual_pct'], errors='raise')
    df['planned_pct'] = pd.to_numeric(df['planned_pct'], errors='raise')
    df['variance_pp'] = pd.to_numeric(df['variance_pp'], errors='raise')
    if (df[['actual_pct', 'planned_pct']].isna().any().any()
            or not df['actual_pct'].between(0, 100).all()
            or not df['planned_pct'].between(0, 100).all()):
        raise ValueError('Gantt requires completion percentages between 0 and 100')
    snap = pd.Timestamp(snapshot).normalize()

    def state(row):
        if row['actual_pct'] >= 100:
            return 'Completed'
        if row['variance_pp'] < -10:
            return 'Behind baseline'
        if row['finish_date'] < snap:
            return 'Past finish date'
        return 'In progress' if row['actual_pct'] > 0 else 'Not started'

    df['gantt_status'] = df.apply(state, axis=1)
    df['gantt_label'] = df.apply(
        lambda row: f"{str(row['wbs'])} · {str(row['activity'])[:26]} [{row['activity_id']}]",
        axis=1,
    )
    df['duration_days'] = (df['finish_date'] - df['start_date']).dt.days + 1
    if focus:
        priority = {
            'Behind baseline': 0, 'Past finish date': 1,
            'In progress': 2, 'Not started': 3, 'Completed': 4,
        }
        df['_rank'] = df['gantt_status'].map(priority)
        df['_current'] = (df['start_date'] <= snap) & (df['finish_date'] >= snap)
        df = df.sort_values(
            ['_rank', '_current', 'start_date', 'activity_id'],
            ascending=[True, False, True, True],
        ).head(max(1, limit)).drop(columns=['_rank', '_current'])
    else:
        df = df.sort_values(['start_date', 'activity_id'])
    return df.reset_index(drop=True)


def gantt_figure(activities: pd.DataFrame, snapshot: pd.Timestamp, *,
                 compact: bool = False, limit: int = 6) -> go.Figure:
    """Planned date bars with completion fractions; not observed actual work dates."""
    df = gantt_rows(activities, snapshot, focus=compact, limit=limit)
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text='No activity dates to display', x=.5, y=.5,
                           xref='paper', yref='paper', showarrow=False)
        return _style(fig, 260 if compact else 360, legend=False)
    duration_ms = df['duration_days'].astype(float) * 86_400_000
    custom = df[[
        'activity_id', 'activity', 'owner', 'start_date', 'finish_date',
        'planned_pct', 'actual_pct', 'variance_pp', 'gantt_status',
    ]].copy()
    for col in ('start_date', 'finish_date'):
        custom[col] = custom[col].dt.strftime('%d %b %Y')
    hover_data = custom.astype(str).to_numpy()
    hover_template = (
        '<b>%{customdata[0]} · %{customdata[1]}</b><br>'
        'Owner: %{customdata[2]}<br>'
        'Planned window: %{customdata[3]}–%{customdata[4]}<br>'
        'Linear baseline completion: %{customdata[5]}%<br>'
        'Reported completion: %{customdata[6]}%<br>'
        'Gap: %{customdata[7]} pp<br>'
        'Status: %{customdata[8]}<extra></extra>'
    )
    fig.add_trace(go.Bar(
        x=duration_ms, base=df['start_date'], y=df['gantt_label'],
        orientation='h', name='Planned window', width=.64,
        marker=dict(color=GREY), opacity=.30,
        customdata=hover_data, hovertemplate=hover_template,
    ))
    for state, color in STATUS_COLORS.items():
        part = df.loc[df['gantt_status'].eq(state) & df['actual_pct'].gt(0)]
        if part.empty:
            continue
        indices = part.index.to_numpy()
        fig.add_trace(go.Bar(
            x=duration_ms.loc[indices] * part['actual_pct'].to_numpy() / 100,
            base=part['start_date'], y=part['gantt_label'],
            orientation='h', name=state, width=.37,
            marker=dict(color=color), opacity=.98,
            customdata=hover_data[indices], hovertemplate=hover_template,
        ))
    date = pd.Timestamp(snapshot).normalize()
    fig.add_vline(x=date.timestamp() * 1000,
                  line=dict(color=GOLD, width=2, dash='dash'))
    fig.add_annotation(x=date, y=1.02, xref='x', yref='paper',
                       text='Reporting date', showarrow=False,
                       font=dict(color=GOLD, size=11),
                       bgcolor='rgba(20,30,50,.03)')
    fig.update_layout(barmode='overlay', dragmode='zoom', hovermode='closest')
    fig.update_xaxes(
        type='date', title=None if compact else 'Planned schedule dates',
        tickformat='%d %b', showgrid=True, gridcolor=GRID,
        rangeslider=dict(visible=False),
    )
    fig.update_yaxes(
        categoryorder='array',
        categoryarray=df['gantt_label'].iloc[::-1].tolist(),
        gridcolor='rgba(0,0,0,0)', title=None,
        tickmode='array', tickvals=df['gantt_label'].tolist(),
        ticktext=[
            f"{row['wbs']} · {str(row['activity'])[:11 if compact else 17]}"
            f"{'…' if len(str(row['activity'])) > (11 if compact else 17) else ''}"
            for _, row in df.iterrows()
        ],
        tickfont=dict(size=10 if compact else 11), automargin=True,
    )
    fig = _style(
        fig,
        max(270, 40 * len(df) + 72) if compact else max(280, 43 * len(df) + 96),
    )
    fig.update_layout(
        margin=dict(l=8, r=16, t=12 if compact else 28, b=34 if compact else 70),
        showlegend=not compact,
        legend=dict(orientation='h', y=-.24, x=0, font=dict(size=10)),
    )
    return fig
