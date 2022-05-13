from z3 import Int, Real, IntVector, RealVector, Sum, Product, Optimize, sat
import random
import os
try:
    import ujson as json
except:
    import json
import copy

_words = {
    'en': {
        'max': 'maximum',
        'min': 'minimum',
    },
    'zh': {
        'max': '最大',
        'min': '最小',
    }
}

class _Objective:
    def __init__(self, obj, verbose=False):

        if 'goal' not in obj:
            if verbose:
                print('Cannot find goal in objective. Use max as default.')
            self.goal = 'max'
        else:
            self.goal = obj['goal']

        if self.goal not in ('min', 'max'):
            raise Exception('Illegal goal: need to be min or max')
        
        if 'type' not in obj:
            if verbose:
                print('Cannot find type in objective. Use int as default.')
            self.type = 'int'
        else:
            self.type = obj['type']
        
        if self.type not in ('int', 'real'):
            raise Exception('Illegal type: need to be int or real')
        
        # words like '最小' or '最大'
        # index: [start, end] (inclusive)
        if 'index' not in obj:
            raise Exception('Need index in objective as \'index\'')
        self.index = obj['index']


class _Variable:
    def __init__(self, obj, verbose=False):
        if 'count' not in obj:
            raise Exception('Need count in variable as \'count\'')
        self.count = obj['count']
            
        if 'type' not in obj:
            if verbose:
                print('Cannot find type in variable. Use int as default.')
            self.type = 'int'
        else:
            self.type = obj['type']
        
        if self.type not in ('int', 'real'):
            raise Exception('Illegal type: need to be int or real')


class _Constraint:
    def __init__(self, obj, upbound, numvar, dep=1, verbose=False):
        if 'term' not in obj:
            raise Exception('Need term in constraint as \'term\'')
        self.term = obj['term']

        self.upbound = upbound
        self.numvar = numvar

        if isinstance(self.term, str):
            if 'comp' not in obj:
                raise Exception('Need comp in constraint as \'comp\'')
            self.comp = obj['comp']

            if 'rval' not in obj:
                raise Exception('Need rval in constraint as \'rval\'')
            self.rval = obj['rval']
        else:
            self.comp = None
            self.rval = None

        # the index of the rval
        if 'index' in obj:
            self.index = obj['index']

        if 'type' not in obj:
            if verbose:
                print('Cannot find constraint type. Parsing as single by default.')
            self.type = 'single'
        else:
            self.type = obj['type']
            if self.type not in ('single', 'loop', 'sum', 'product'):
                raise Exception('Illegal constraint type.')
        
        if self.type in ('loop', 'sum', 'product'):
            if 'range' not in obj:
                if verbose:
                    print('Cannot find range. Using [1,{}] as default.'.format(upbound))
                self.range = [1, upbound]
            else:
                self.range = obj['range']

            if 'loopvar' not in obj:
                if verbose:
                    print('Cannot find loopvar. Using i_{} as default.'.format(dep))
                self.loopvar = 'i_{}'.format(dep)
            else:
                self.loopvar = obj['loopvar']
        
        if obj['type'] == 'loop':
            if isinstance(self.term, dict):
                self.term = [_Constraint(self.term, self.loopvar, numvar, dep+1, verbose)]
            elif isinstance(self.term, list):
                self.term = [_Constraint(t, self.loopvar, numvar, dep+1, verbose) for t in self.term]
    
    def _print(self, level=0):
        padding = '\t' * level
        print(padding, 'This is a constraint of type {}:'.format(self.type), sep='')

        if self.type == 'single':
            print(padding, '{} {} {}'.format(self.term, self.comp, self.rval), sep='\t')
        elif self.type == 'loop':
            print(padding, 'For value {} in range [{},{}]: '.format(self.loopvar, self.range[0], self.range[1]), sep='\t', end='')
            
            if isinstance(self.term, str):
                print('{} {} {}'.format(self.term, self.comp, self.rval))
            else:
                print('the following constraints holds:')
                for t in self.term:
                    t._print(level+1)
        else:
            if self.range[0]==1 and self.range[1]==self.numvar:
                term = self.term
            else:
                term = '[{} for {} in [{},{}]]'.format(self.term, self.loopvar, self.range[0], self.range[1], )
            print(padding, '{}({}) {} {}'.format(self.type, term, self.comp, self.rval), sep='\t')


class _Input:
    def __init__(self, obj, verbose=False):
        if 'name' not in obj:
            raise Exception('Need name in input as \'name\'')
        self.name = obj['name']

        reserved = ('x', 'y')
        if self.name in reserved:
            raise Exception('Illegal name: {} is reserved'.format(self.name))

        if 'type' not in obj:
            if verbose:
                print('Cannot find input type. Parsing as int by default.')
            self.type = 'int'
        else:
            self.type = obj['type']
            if self.type not in ('int', 'real', 'intarray', 'realarray'):
                raise Exception('Illegal input type.')
            
        if self.type in ('intarray', 'realarray'):
            if 'length' not in obj:
                raise Exception('Need length in input as \'length\'')
            self.length = obj['length']



class ProblemModel:
    def __init__(self, file_path=None, encoding='utf-8', verbose=False):
        self.json = None
        self.problem_text = None
        self.objective = None
        self.variable = None
        self.constraint = None
        self.input = None
        self.verbose = verbose

        if file_path == None or not os.path.exists(file_path):
            raise Exception('Illegal file path')

        with open(file_path, encoding=encoding) as f:
            self.json = json.load(f)
        
        self._parse(self.json)
    
    def _parse(self, js):
        if 'language' not in js:
            print('Cannot find language. Using zh by default.')
            self.lang = 'zh'
        else:
            self.lang = js['language']

        if 'text' not in js:
            raise Exception('Need problem text as \'text\'')
        self.problem_text = js['text']

        if 'objective' not in js:
            raise Exception('Need objective as \'objective\'')
        obj = js['objective']
        self.objective = _Objective(obj, self.verbose)

        if 'variable' not in js:
            raise Exception('Need variable as \'variable\'')
        obj = js['variable']
        self.variable = _Variable(obj, self.verbose)

        if 'constraint' in js:
            self.constraint = []
            Obj = js['constraint']
            if isinstance(Obj, list):
                for obj in Obj:
                    self.constraint.append(_Constraint(obj, self.variable.count, self.variable.count,1,self.verbose))
            elif isinstance(Obj, dict):
                self.constraint.append(_Constraint(Obj, self.variable.count, self.variable.count, 1, self.verbose))
        
        if 'input' in js:
            self.input = []
            Obj = js['input']
            for obj in Obj:
                self.input.append(_Input(obj, self.verbose))
    
    def mutate(self, mode=None):
        modes = ('objective', 'constraint')
        if mode==None:
            mode = random.choice(modes)
        elif mode not in modes:
            raise Exception('Illegal mode: {}'.format(mode))
        
        if mode=='objective':
            pass
        elif mode=='constraint':
            pass
        else:
            pass

    def print(self):
        print('This problem has {} variables of type {}.'.format(self.variable.count, self.variable.type))
        
        print('This problem has {} constraints:'.format(len(self.constraint)))
        for i,c in enumerate(self.constraint):
            print('Constraint {}:'.format(i+1))
            c._print()
        
        print('This problem has {} inputs:'.format(len(self.input)))
        for i,c in enumerate(self.input):
            print('Input {}:'.format(i+1))
            print('\tName: {}'.format(c.name))
            print('\tType: {}'.format(c.type))
            if c.type in ('intarray', 'realarray'):
                print('\tLength: {}'.format(c.length))
    
    @staticmethod
    def _get_number(i,val_dict):
        def is_number(s, tp=int):
            try:
                tp(s)
                return True
            except ValueError:
                return False

        if isinstance(i, int) or isinstance(i, float):
            return i
        elif isinstance(i, str):
            if is_number(i, int):
                return int(i)
            elif is_number(i, float):
                return float(i)
            elif i in val_dict:
                return val_dict[i]
            else:
                raise Exception('Cannot find value {}'.format(i))
        else:
            raise Exception('Illegal type: {}'.format(type(i)))
    
    @staticmethod
    def _parse_constraint(con, _val, x, y, opt, verbose=False):
        
        _val['x'] = x
        _val['y'] = y
        
        comp_func = {
            '<': lambda x,y: x<y,
            '<=': lambda x,y: x<=y,
            '>': lambda x,y: x>y,
            '>=': lambda x,y: x>=y,
            '=': lambda x,y: x==y,
        }
        def get_comp(comp):
            if comp in comp_func:
                return comp_func[comp]
            else:
                raise Exception('Illegal comparison operator: {}'.format(comp))

        if con.type in ('single', 'sum', 'product'):
            if con.type == 'single':
                term = con.term
            else:
                term = '[{} for {} in range({},{})]'.format(
                    con.term, con.loopvar, con.range[0]-1, con.range[1])
            term = eval(term, _val)
            rval = eval(con.rval, _val)
            if con.type == 'sum':
                term = Sum(term)
            elif con.type == 'product':
                term = Product(term)
            
            final = get_comp(con.comp)(term, rval)
            if verbose:
                print('Adding constraint:', final)
            opt.add(final)
        
        elif con.type == 'loop':
            lbound = ProblemModel._get_number(con.range[0], _val)
            ubound = ProblemModel._get_number(con.range[1], _val)
            
            if con.loopvar in _val:
                raise Exception('Loop variable {} already exists.'.format(con.loopvar))
            
            for i in range(lbound-1, ubound):
                _val[con.loopvar] = i
                if isinstance(con.term, str):
                    term = eval(con.term, _val)
                    rval = eval(con.rval, _val)
                    final = get_comp(con.comp)(term, rval)
                    if verbose:
                        print('Adding constraint:', final)
                    opt.add(final)
                else:
                    _val[con.loopvar] = i+1
                    for cons in con.term:
                        ProblemModel._parse_constraint(cons, _val, x, y, opt, verbose)
            
            del _val[con.loopvar]
        
        else:
            raise Exception('Illegal constraint type: {}'.format(con.type))

            

    def _input(self):
        input_dict = {}
        for i in self.input:
            if i.name in input_dict:
                raise Exception('Duplicate input name: {}'.format(i.name))

            if i.type in ('int', 'real'):
                print('Input {}, a {} number: '.format(i.name, i.type), end='')
                tp = int if i.type == 'int' else float
                try:
                    input_dict[i.name] = tp(input())
                except ValueError:
                    raise Exception('Illegal input')
                
            
            elif i.type in ('intarray', 'realarray'):
                tp = int if i.type == 'intarray' else float

                length = ProblemModel._get_number(i.length, input_dict)
                
                print('Input {}, a {} of length {}: '.format(i.name, i.type, length,), end='')
                try:
                    input_dict[i.name] = [tp(v) for v in input().split()]
                except ValueError:
                    raise Exception('Illegal input')
                
                if len(input_dict[i.name]) != length:
                    raise Exception('Input length mismatch: {} != {}'.format(len(input_dict[i.name]), length)) 
            
            else:
                raise Exception('Illegal input type: {}'.format(i.type))
        
        return input_dict
    
    def solve(self, verbose = False):
        # first, handle input
        value_dict = self._input()

        # declare optimizer, variable x, and goal y
        opt = Optimize()

        num_var = ProblemModel._get_number(self.variable.count, value_dict)
        if self.variable.type == 'int':
            x = IntVector('x', num_var)
        else:
            x = RealVector('x', num_var)
        
        if self.objective.type == 'int':
            y = Int('y')
        else:
            y = Real('y')

        # handle constraints
        # need to do a recursive way
        for con in self.constraint:
            ProblemModel._parse_constraint(con, value_dict, x, y, opt, verbose)
        
        h = opt.maximize(y) if self.objective.goal == 'max' else opt.minimize(y)
        if opt.check() != sat:
            return False, None
        if self.objective.goal == 'max':
            return opt.upper(h), opt.model()
        else:
            return opt.lower(h), opt.model()