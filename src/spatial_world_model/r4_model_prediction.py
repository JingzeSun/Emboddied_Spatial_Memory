"""D-096 framework-free conversion of model task values to the R4 contract."""
import math
from .r4_query_v2 import PREDICTION_VERSION,validate_prediction,mean_predictions


def sigmoid(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('task logit must be finite')
    if value>=0:return 1/(1+math.exp(-value))
    exponent=math.exp(value)
    return exponent/(1+exponent)


def pack(position_m,contact_logit,success_logit):
    result={'schema_version':PREDICTION_VERSION,'prediction_times_s':[i/10 for i in range(1,201)],
            'object_position_m':position_m,'obstacle_contact_probability':[sigmoid(v) for v in contact_logit],
            'task_success_probability':sigmoid(success_logit)}
    validate_prediction(result)
    return result


def aggregate(samples):
    """One deterministic output or sixteen stochastic probability samples."""
    return mean_predictions(samples)
