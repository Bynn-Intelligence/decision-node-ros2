# One answer, under the id of the question it answers. A field the answer's type does
# not carry is NaN (a number), 0 (count) or empty (a string or an array).

string id
string type                # truth, choice, score, number, point, box, or unknown

float64 truth              # truth: the probability that the answer is yes, 0 to 1
string choice              # choice: the option chosen
float64 score              # score: the expected level index, from 0
float64 number             # number: the most probable value
float64 expected           # number: the probability-weighted mean
float64 confidence         # choice, score, number, point, box

float64 present            # point, box: the probability that the thing is in the image
float64[] place            # point: [x, y]; box: [x1, y1, x2, y2]; asked with max, every
                           # place found, one after the other
float64[] place_confidence # asked with max: each place's own confidence
int32 count                # asked with max: how many places were found
float64 complete           # asked with max: the probability that nothing was left out
string image               # point, box: the id of the image looked in
int32 width                # point, box: the image's width in pixels
int32 height               # point, box: the image's height in pixels

string[] labels            # choice, score, number: the keys of probabilities, in order
float64[] probabilities    # the probability of each label

string raw_json            # the answer exactly as the API sent it
