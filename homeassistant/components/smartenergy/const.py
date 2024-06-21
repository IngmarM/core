"""Constants re-used across different files."""

# Configuration

DOMAIN = "smartenergy"
CONF_OUTPUT_SOURCE_INTEGRATION = "output_source_integration"
CONF_OUTPUT_SOURCE = "output_source"
CONF_INPUT_SOURCE = "input_source"
CONF_CONSUMERS = "consumers"
CONF_SMART_ENERGY_MODE = "smart_energy_mode"
CONF_HOURS_TO_CHARGE = "hours_to_charge"
CONF_CHARGING_TIME_WINDOW_HOURS = "charging_time_window_hours"

DOMAIN_GO_E_CHARGER = "smartenergy_goecharger"

# State

INIT_STATE = "init"
MAIN_COORDINATOR_NAME = "main_coordinator"
CHARGING_SCHEDULES = "charging_schedules"
UNSUB_OPTIONS_UPDATE_LISTENER = "unsub_options_update_listener"
CURRENT_SCHEDULE_START = "current_schedule_start"
CURRENT_SCHEDULE_END = "current_schedule_end"
CURRENT_SCHEDULES = "current_schedules"
CURRENT_CYCLE_HOURS_TO_CHARGE = "current_cycle_hours_to_charge"
CURRENT_CYCLE_CHARGING_TIME_WINDOW_HOURS = "current_cycle_charging_time_window_hours"
CURRENT_CYCLE_CHARGING_TIME_WINDOW_DATE = "current_cycle_charging_time_window_date"
START_SCHEDULED_CHARGING = "start_scheduled_charging"

SIMPLE = "simple"
PRECISE = "precise"

START_TIME = "start_time"
MARKET_PRICE = "marketprice"
VALUE = "value"
FORECAST = "forecast"
SCHEDULES = "schedules"

# Attributes

ENABLED = "enabled"
SCHEDULER_ENABLED = "scheduler_enabled"
MANUFACTURER = "KfW"

# Other integrations

SMARTENERGY_AWATTAR = "smartenergy_awattar_forecast"
