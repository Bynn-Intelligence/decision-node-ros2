# The answers to the configured questions about one frame, or why there are none.

std_msgs/Header header     # the stamp and frame_id of the frame answered

bool ok                    # false: no answers; see error_type and error_message
Answer[] answers           # one per question, in the order of the parameter questions.ids

string request_id          # the API's request id, for support
string model               # the model version that answered
float64 latency_ms         # the API's own time for the request
float64 cost_usd           # what the request cost, as the API booked it; NaN when not sent
string evidence_json       # the boosters' readings exactly as the API sent them, as JSON:
                           # booster name to its version, status and results; empty when
                           # the request named no booster

string error_type          # empty when ok, else the API's error_type or the error's kind
string error_message
uint32 frames_dropped      # frames left unanswered by the rate limit since the last decision
