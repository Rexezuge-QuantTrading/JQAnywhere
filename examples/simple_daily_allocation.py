from jqdata import *


def initialize(context):
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")
    run_daily(trade, "09:50")


def trade(context):
    order_target_value("000300.XSHG", context.portfolio.total_value)
