-- Staging: typed views over the raw CSV extracts.
create schema if not exists staging;

create or replace view staging.projects as
select project_code, project_name, district, project_type,
       cast(start_date as date) as start_date, cast(planned_finish as date) as planned_finish,
       cast(budget_try as decimal(18, 2)) as budget_try
from read_csv_auto('data/raw/projects.csv', header = true);

create or replace view staging.budget_lines as
select project_code, lpad(cast(cost_code as varchar), 2, '0') as cost_code, cost_category,
       cast(budget_try as decimal(18, 2)) as budget_try
from read_csv_auto('data/raw/budget_lines.csv', header = true, types = {'cost_code': 'VARCHAR'});

create or replace view staging.planned_spend as
select project_code, lpad(cast(cost_code as varchar), 2, '0') as cost_code, cast(month as date) as month,
       cast(planned_value_try as decimal(18, 2)) as planned_value_try
from read_csv_auto('data/raw/planned_spend.csv', header = true, types = {'cost_code': 'VARCHAR'});

create or replace view staging.progress as
select project_code, lpad(cast(cost_code as varchar), 2, '0') as cost_code, cast(month as date) as month,
       cast(pct_complete as double) / 100 as pct_complete
from read_csv_auto('data/raw/progress.csv', header = true, types = {'cost_code': 'VARCHAR'});

create or replace view staging.actual_costs as
select invoice_id, project_code, lpad(cast(cost_code as varchar), 2, '0') as cost_code,
       cast(invoice_date as date) as invoice_date, date_trunc('month', cast(invoice_date as date))::date as month,
       vendor, cast(amount_try as decimal(18, 2)) as amount_try
from read_csv_auto('data/raw/actual_costs.csv', header = true, types = {'cost_code': 'VARCHAR'});

create or replace view staging.change_orders as
select change_order_id, project_code, lpad(cast(cost_code as varchar), 2, '0') as cost_code,
       cast(raised_on as date) as raised_on, status, cast(amount_try as decimal(18, 2)) as amount_try, reason
from read_csv_auto('data/raw/change_orders.csv', header = true, types = {'cost_code': 'VARCHAR'});
