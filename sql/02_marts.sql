-- Marts: earned value management (EVM) at cost-category and project level.
create schema if not exists marts;

-- One row per project × cost category × reporting month, with cumulative PV, EV and AC.
create or replace table marts.evm_category_monthly as
with months as (
    select distinct project_code, month from staging.progress
),
grid as (
    select m.project_code, b.cost_code, b.cost_category, b.budget_try, m.month
    from months m join staging.budget_lines b using (project_code)
),
pv as (
    select g.project_code, g.cost_code, g.month, sum(p.planned_value_try) as pv_cum
    from grid g join staging.planned_spend p
      on p.project_code = g.project_code and p.cost_code = g.cost_code and p.month <= g.month
    group by all
),
ac as (
    select g.project_code, g.cost_code, g.month, coalesce(sum(a.amount_try), 0) as ac_cum
    from grid g left join staging.actual_costs a
      on a.project_code = g.project_code and a.cost_code = g.cost_code and a.month <= g.month
    group by all
)
select
    g.project_code, g.cost_code, g.cost_category, g.month, g.budget_try as bac,
    coalesce(pv.pv_cum, 0)                                   as pv,
    round(coalesce(pr.pct_complete, 0) * g.budget_try, 2)    as ev,
    ac.ac_cum                                                as ac,
    coalesce(pr.pct_complete, 0)                             as pct_complete
from grid g
left join pv using (project_code, cost_code, month)
left join ac using (project_code, cost_code, month)
left join staging.progress pr using (project_code, cost_code, month);

-- Project S-curve: cumulative PV, EV and AC per month.
create or replace table marts.evm_project_monthly as
select project_code, month,
       sum(bac) as bac, sum(pv) as pv, sum(ev) as ev, sum(ac) as ac,
       round(sum(ev) / nullif(sum(ac), 0), 3) as cpi,
       round(sum(ev) / nullif(sum(pv), 0), 3) as spi
from marts.evm_category_monthly
group by all;

-- Status at the latest reporting month, with forecasts.
create or replace table marts.project_status as
with latest as (
    select * from marts.evm_project_monthly
    qualify row_number() over (partition by project_code order by month desc) = 1
),
co as (
    select project_code,
           sum(case when status = 'Approved' then amount_try else 0 end) as approved_changes,
           sum(case when status = 'Pending' then amount_try else 0 end)  as pending_changes,
           count(*) filter (where status = 'Approved')                   as approved_count
    from staging.change_orders group by 1
)
select
    p.project_code, p.project_name, p.district, p.project_type, p.start_date, p.planned_finish,
    l.month                                                       as status_month,
    l.bac,
    coalesce(co.approved_changes, 0)                              as approved_changes,
    coalesce(co.pending_changes, 0)                               as pending_changes,
    coalesce(co.approved_count, 0)                                as approved_change_orders,
    l.bac + coalesce(co.approved_changes, 0)                      as revised_budget,
    l.pv, l.ev, l.ac,
    round(l.ev / l.bac, 4)                                        as pct_complete,
    l.cpi, l.spi,
    round(l.ev - l.ac, 2)                                         as cost_variance,
    round(l.ev - l.pv, 2)                                         as schedule_variance,
    round(l.bac / l.cpi, 2)                                       as eac,                     -- estimate at completion
    round(l.bac / l.cpi - l.ac, 2)                                as etc,                     -- estimate to complete
    round(l.bac - l.bac / l.cpi, 2)                               as vac,                     -- variance at completion
    round((l.bac - l.ev) / nullif(l.bac - l.ac, 0), 3)            as tcpi,                    -- efficiency needed to finish on budget
    (p.start_date + to_months(cast(round(date_diff('month', p.start_date, p.planned_finish) / l.spi) as integer)))::date as forecast_finish,
    case
        when l.cpi < 0.95 or l.spi < 0.90 then 'At risk'
        when l.cpi < 1.00 or l.spi < 0.97 then 'Watch'
        else 'On track'
    end                                                           as health
from staging.projects p
join latest l using (project_code)
left join co using (project_code);

-- Category variance for the latest month (where the money goes wrong).
create or replace table marts.category_variance as
select c.project_code, c.cost_code, c.cost_category, c.bac, c.pv, c.ev, c.ac,
       round(c.ev - c.ac, 2) as cost_variance,
       round(c.ev / nullif(c.ac, 0), 3) as cpi,
       round(c.ev / nullif(c.pv, 0), 3) as spi
from marts.evm_category_monthly c
join marts.project_status s on s.project_code = c.project_code and s.status_month = c.month;

create or replace table marts.vendor_spend as
select project_code, vendor, round(sum(amount_try), 2) as spend_try, count(*) as invoices
from staging.actual_costs group by all;
