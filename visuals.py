"""Executive-grade, explainable Plotly figures for the PEIMS *fictional* demo.

These figures use only validated project snapshots. They are NOT predictive AI,
not an approved risk methodology, and not a Primavera/SAP substitute.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

NAVY = '#0b1625'
GRID = 'rgba(156,181,204,.18)'
INK = '#dce7f1'
MUTED = '#a2b7cb'
TEAL = '#40c9b9'    # actual / favourable
GOLD = '#f0ba66'    # baseline / caution
RED = '#f4777b'     # delay / adverse
BLUE = '#80acdc'    # reference / neutral
GREY = '#71879a'


def _style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=22, r=18, t=35, b=38),
        font=dict(family='Arial, sans-serif', size=12, color=INK),
        hoverlabel=dict(bgcolor='#1b3046', font=dict(color='#fff', size=12)),
        legend=dict(orientation='h', y=1.15, x=0, bgcolor='rgba(0,0,0,0)'),
        showlegend=legend,
        hovermode='closest',
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GREY, showline=False)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GREY, showline=False)
    return fig


def progress_s_curve(history: pd.DataFrame, snapshot: pd.Timestamp) -> go.Figure:
    """Two *observed* weekly progress lines, no invented future points."""
    df = history.copy().sort_values('week_ending')
    fig = go.Figure()
    for field, name, color in [
        ('planned_pct', 'Historical baseline', GOLD),
        ('actual_pct', 'Reported actual', TEAL),
    ]:
        fig.add_trace(go.Scatter(
            x=df['week_ending'], y=df[field],
            mode='lines+markers', name=name,
            line=dict(color=color, width=3, shape='linear'),
            marker=dict(size=7, line=dict(color=NAVY, width=1)),
            hovertemplate='%{x|%d %b %Y}<br>'+name+': <b>%{y:.1f}%</b><extra></extra>',
        ))
    if not df.empty:
        last = df.iloc[-1]
        gap = float(last['actual_pct'] - last['planned_pct'])
        fig.add_annotation(x=last['week_ending'], y=last['actual_pct'],
                           text=f'Latest reported gap {gap:+.1f} pp',
                           showarrow=True, arrowhead=2, ax=-100, ay=48,
                           font=dict(color=RED if gap < 0 else TEAL, size=11),
                           bgcolor='#15283e', bordercolor=GRID, borderpad=5)
    fig.update_yaxes(title='Weighted completion (%)', range=[0, 105], ticksuffix='%')
    fig.update_xaxes(title='Reporting week')
    return _style(fig, 385)


def schedule_variance(activities: pd.DataFrame) -> go.Figure:
    """Dumbbell view shows baseline vs actual; colour communicates size/direction."""
    df = activities.copy().sort_values('variance_pp', ascending=False)
    fig = go.Figure()
    for i, (_, row) in enumerate(df.iterrows()):
        fig.add_trace(go.Scatter(
            x=[float(row['planned_pct']), float(row['actual_pct'])], y=[i, i],
            mode='lines', line=dict(color='rgba(170,190,210,.42)', width=3),
            hoverinfo='skip', showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=df['planned_pct'], y=list(range(len(df))),
        mode='markers', name='Baseline', marker=dict(color=GOLD, size=9, symbol='circle-open', line=dict(width=2)),
        customdata=df[['activity_id', 'activity']].astype(str).to_numpy(),
        hovertemplate='%{customdata[0]} · %{customdata[1]}<br>Baseline: %{x:.1f}%<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=df['actual_pct'], y=list(range(len(df))),
        mode='markers', name='Actual',
        marker=dict(color=[RED if v < -10 else (TEAL if v >= 0 else GOLD) for v in df['variance_pp']],
                    size=12, line=dict(width=1, color=NAVY)),
        customdata=df[['activity_id', 'activity', 'variance_pp', 'owner']].astype(str).to_numpy(),
        hovertemplate='%{customdata[0]} · %{customdata[1]}<br>Actual: %{x:.1f}%<br>Gap: %{customdata[2]} pp<br>Owner: %{customdata[3]}<extra></extra>',
    ))
    fig.update_yaxes(tickmode='array', tickvals=list(range(len(df))),
                     ticktext=[f"{r.activity_id} · {str(r.activity)[:31]}" for r in df.itertuples()],
                     zeroline=False, gridcolor='rgba(0,0,0,0)', autorange='reversed')
    fig.update_xaxes(title='Physical completion (%)', range=[0, 105], ticksuffix='%')
    return _style(fig, max(380, 48 * len(df) + 90))


def dependency_timeline(activities: pd.DataFrame, cpm: dict, snapshot: pd.Timestamp) -> go.Figure:
    """Calendar-day CPM *modelled* dates, criticality and reporting cut-off."""
    network = pd.DataFrame(cpm['activities'])
    df = activities.merge(network[['activity_id', 'earliest_start', 'earliest_finish', 'critical', 'total_float_days']],
                          on='activity_id', validate='one_to_one')
    df['earliest_start'] = pd.to_datetime(df['earliest_start'])
    df['earliest_finish'] = pd.to_datetime(df['earliest_finish'])
    df = df.sort_values(['earliest_start', 'activity_id'])
    fig = go.Figure()
    for is_critical, label, color in [(False, 'Noncritical', BLUE), (True, 'Critical path', RED)]:
        part = df[df['critical'] == is_critical]
        if part.empty:
            continue
        days = (part['earliest_finish'] - part['earliest_start']).dt.days + 1
        additional = part[['activity','total_float_days','actual_pct','owner']].copy()
        additional['duration_days'] = days.values
        fig.add_trace(go.Bar(
            x=days * 86_400_000, base=part['earliest_start'],
            y=part['activity_id'], orientation='h', name=label,
            marker=dict(color=color, line=dict(width=0)), opacity=.86,
            customdata=part[['activity','total_float_days','actual_pct','owner']].astype(str).to_numpy(),
            hovertemplate='%{y} · %{customdata[0]}<br>Modelled duration: %{x} ms<br>Float: %{customdata[1]} days<br>Actual: %{customdata[2]}%<br>Owner: %{customdata[3]}<extra></extra>',
        ))
    fig.add_vline(x=pd.Timestamp(snapshot).timestamp()*1000, line=dict(color=GOLD, width=2, dash='dash'))
    fig.add_annotation(x=pd.Timestamp(snapshot), y=1.01, xref='x', yref='paper',
                       text='Reporting cut-off', showarrow=False, font=dict(color=GOLD, size=11))
    fig.update_layout(barmode='overlay')
    fig.update_xaxes(type='date', title='Modelled calendar dates')
    fig.update_yaxes(categoryorder='array', categoryarray=df['activity_id'].iloc[::-1].tolist(),
                     gridcolor='rgba(0,0,0,0)', title='WBS activity ID')
    return _style(fig, max(380, 43 * len(df) + 110))


def cost_variance_waterfall(kpi: dict, currency: str) -> go.Figure:
    """AC + (EV−AC) = EV, a transparent cost-efficiency bridge."""
    ac, ev = float(kpi['actual_cost']), float(kpi['earned_value'])
    cv = ev - ac
    fig = go.Figure(go.Waterfall(
        orientation='v', measure=['absolute', 'relative', 'total'],
        x=['Recorded actual cost', 'Cost variance (EV−AC)', 'Earned value'],
        y=[ac, cv, 0], text=[f'{ac:,.0f}', f'{cv:+,.0f}', f'{ev:,.0f}'], textposition='outside',
        increasing=dict(marker=dict(color=TEAL)),
        decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color=BLUE)),
        connector=dict(line=dict(color=GREY, dash='dot')),
        hovertemplate='%{x}<br>%{y:,.0f} '+currency+'<extra></extra>',
    ))
    fig.update_yaxes(title=currency, rangemode='tozero', tickformat=',.0f')
    return _style(fig, 390, False)


def cost_exposure_quadrant(activities: pd.DataFrame, currency: str) -> go.Figure:
    """Cross-project trade-off: schedule gap vs earned value less actual cost by activity."""
    df = activities.copy()
    df['cost_variance'] = df['earned_value'] - df['actual_cost']
    df['point_size'] = (np.sqrt(df['baseline_budget'].clip(lower=0) / max(1., float(df['baseline_budget'].max()))) * 28 + 9).clip(9, 38)
    severity = (df['variance_pp'] < -10) | (df['cost_variance'] < 0)
    fig = go.Figure(go.Scatter(
        x=df['variance_pp'], y=df['cost_variance'], mode='markers',
        marker=dict(size=df['point_size'], color=[RED if v else TEAL for v in severity],
                    opacity=.78, line=dict(color=NAVY, width=1.5)),
        customdata=df[['activity_id','activity','baseline_budget','owner']].astype(str).to_numpy(),
        text=df['activity_id'], textposition='top center',
        hovertemplate='%{customdata[0]} · %{customdata[1]}<br>Progress gap: %{x:+.1f} pp'
                      f'<br>Cost variance: %{{y:+,.0f}} {currency}'
                      '<br>Budget: %{customdata[2]}<br>Owner: %{customdata[3]}<extra></extra>',
    ))
    fig.add_hline(y=0, line=dict(color=GREY, dash='dash', width=1.5))
    fig.add_vline(x=0, line=dict(color=GREY, dash='dash', width=1.5))
    fig.update_xaxes(title='Physical progress variance (actual − baseline, pp)', ticksuffix=' pp')
    fig.update_yaxes(title=f'Cost variance (EV − AC), {currency}', tickformat=',.0f', zeroline=True)
    return _style(fig, 410, False)


def procurement_delivery_map(procurement: pd.DataFrame, snapshot: pd.Timestamp, currency: str) -> go.Figure:
    """Date/value exposure map; size scales with PO value, not overstated delay."""
    p = procurement.copy()
    p['severity'] = np.select(
        [p['overdue'] & p['critical'].astype(str).str.casefold().isin(['yes','true','1']),
         p['overdue'], p['received']],
        ['Critical overdue', 'Overdue', 'Received'], default='On schedule')
    colors={'Critical overdue':RED,'Overdue':GOLD,'On schedule':BLUE,'Received':TEAL}
    fig = go.Figure()
    for label in ('Critical overdue','Overdue','On schedule','Received'):
        group=p.loc[p['severity'].eq(label)]
        if group.empty:
            continue
        max_value=max(1.0, float(p['po_value'].max()))
        sizes=12+30*np.sqrt(group['po_value'].clip(lower=0)/max_value)
        fig.add_trace(go.Scatter(
            x=group['expected_date'], y=group['po_value'], mode='markers',
            name=label,
            marker=dict(size=sizes, color=colors[label], opacity=.82,
                        line=dict(color=NAVY, width=1.4)),
            customdata=group[['po_id','item','supplier','status','days_late']].astype(str).to_numpy(),
            hovertemplate='%{customdata[0]} · %{customdata[1]}<br>Supplier: %{customdata[2]}'
                          '<br>Expected: %{x|%d %b %Y}<br>Value: %{y:,.0f} '
                          + currency + '<br>Status: %{customdata[3]}<br>Days late: %{customdata[4]}<extra></extra>',
        ))
    fig.add_vline(x=pd.Timestamp(snapshot).timestamp()*1000, line=dict(color=GREY, dash='dash', width=1.5))
    fig.update_xaxes(title='Expected delivery date', type='date')
    fig.update_yaxes(title=f'Purchase order value ({currency})', tickformat=',.0f', rangemode='tozero')
    return _style(fig, 400)


def risk_severity_matrix(risks: pd.DataFrame) -> go.Figure:
    """Background reflects score P×I, while label reflects actual OPEN-risk count."""
    p=risks.loc[risks['open']].copy()
    counts=pd.crosstab(p['impact'], p['probability']).reindex(index=range(1,6), columns=range(1,6), fill_value=0)
    score=np.outer(np.arange(1,6), np.arange(1,6))
    fig=go.Figure(go.Heatmap(
        x=list(range(1,6)), y=list(range(1,6)), z=score,
        text=counts.to_numpy(), texttemplate='%{text} open',
        textfont=dict(size=12, color='white'),
        colorscale=[[0,'#23483d'],[.32,'#397358'],[.33,'#98793f'],[.56,'#b99048'],[.57,'#a34244'],[1,'#c65a60']],
        zmin=0,zmax=25, zsmooth=False,
        colorbar=dict(title='P × I', thickness=12),
        hovertemplate='Probability: %{x}<br>Impact: %{y}<br>Score: %{z}<br>Open risks: %{text}<extra></extra>',
        xgap=2,ygap=2,
    ))
    fig.update_xaxes(title='Probability (1–5)',tickvals=[1,2,3,4,5])
    fig.update_yaxes(title='Impact (1–5)',tickvals=[1,2,3,4,5],scaleanchor='x',scaleratio=1)
    return _style(fig, 390, False)


def insight_summary(result: dict) -> list[str]:
    """Transparent, deterministic narrative—no predictive/LLM claims."""
    k=result['kpi']
    out=[]
    gap=float(k['progress_gap'])
    out.append(f"Weighted physical completion is {abs(gap):.1f} pp {'behind' if gap < 0 else 'ahead of' if gap > 0 else 'equal to'} the linear baseline.")
    if k['critical_overdue_po']:
        out.append(f"{k['critical_overdue_po']} critical purchase order(s) are beyond expected receipt dates; verify interfaces and schedule dependencies.")
    if k['cpi'] is not None:
        out.append(f"The CPI is {k['cpi']:.2f}; {'recorded cost exceeds earned value' if k['cpi'] < 1 else 'earned value covers recorded cost' if k['cpi'] > 1 else 'earned and actual costs are equal'} at this snapshot.")
    return out
