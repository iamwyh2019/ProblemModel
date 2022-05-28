import argparse
from ProblemModel import ProblemModel

parser = argparse.ArgumentParser()
parser.add_argument('filepath', help='path for the problem json file')
parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode', dest='verbose')
args = parser.parse_args()

filepath = args.filepath
verbose = args.verbose

model = ProblemModel(filepath, verbose=verbose)
#model.print()
a,b,c = model.solve(verbose=verbose)
print(a)
print(b)
print(c)

# newmodel = model.mutate('parameter')
# print(newmodel.problem_text)
# newmodel = newmodel.mutate('parameter')
# print(newmodel.problem_text)
# a,b = newmodel.solve(verbose=verbose)
# print(a,b)