from __future__ import annotations


def generate_weights(context, data) -> dict[str, float] | None:
    """Return target weights for the current trading day.

    V0 demo rebalances on the first date and then keeps positions unchanged.
    """
    if context.current_date == context.start_date:
        return {"000001.XSHE": 0.5, "600000.XSHG": 0.5}
    return None
