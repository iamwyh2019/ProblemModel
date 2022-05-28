from z3 import Int, Real, IntVector, RealVector, Sum
from z3 import Product, Optimize, Solver, And, Or, sat, If
import random
import os
try:
    import ujson as json
except:
    import json
import copy
import time

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

        if self.goal not in ('min', 'max', 'exist'):
            raise Exception('Illegal goal: need to be exist, min or max')
        
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

class _Parameter:
    def __init__(self, obj, verbose=False):
        if 'type' not in obj:
            if verbose:
                print('Cannot find type in parameter. Use int as default.')
            self.type = 'int'
        else:
            self.type = obj['type']
        
        if self.type not in ('int', 'real'):
            raise Exception('Illegal type: need to be int or real')
        
        if 'name' not in obj:
            raise Exception('Need name in parameter as \'name\'')
        self.name = obj['name']

        if 'range' not in obj:
            raise Exception('Need range in parameter as \'range\'')
        self.range = obj['range']

        if 'index' not in obj:
            raise Exception('Need index in parameter as \'index\'')
        self.index = obj['index']

        if 'value' not in obj:
            raise Exception('Need value in parameter as \'value\'')
        self.value = obj['value']


class _Variable:
    def __init__(self, obj, verbose=False):
        if 'length' not in obj:
            raise Exception('Need length in variable as \'length\'')
        self.count = obj['length']
            
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
        self.loopvar = None

        self.comp = obj['comp'] if 'comp' in obj else None
        self.rval = obj['rval'] if 'rval' in obj else None

        # the index of the rval
        if 'index' in obj:
            self.index = obj['index']
        else:
            self.index = None

        if 'type' not in obj:
            if verbose:
                print('Cannot find constraint type. Parsing as single by default.')
            self.type = 'single'
        else:
            self.type = obj['type']
            if self.type not in ('single', 'loop', 'sum', 'product', 'or', 'and'):
                raise Exception('Illegal constraint type.')
        
        if self.type in ('loop', 'sum', 'product'):
            if 'range' not in obj:
                if verbose:
                    print('Cannot find range. Using [0,{}-1] as default.'.format(upbound))
                self.range = [0, '{}-1'.format(upbound)]
            else:
                self.range = obj['range']

            if 'loopvar' not in obj:
                if verbose:
                    print('Cannot find loopvar. Using i_{} as default.'.format(dep))
                self.loopvar = 'i_{}'.format(dep)
            else:
                self.loopvar = obj['loopvar']
        
        if self.type in ('loop', 'or', 'and'):
            if isinstance(self.term, dict):
                self.term = [_Constraint(self.term, \
                    self.loopvar or upbound, numvar, dep+1, verbose)]
            elif isinstance(self.term, list):
                self.term = [_Constraint(t, \
                    self.loopvar or upbound, numvar, dep+1, verbose) for t in self.term]
    
    def _print(self, level=0):
        padding = '\t' * level
        print(padding, 'This is a constraint of type {}:'.format(self.type), sep='')

        if self.type == 'single':
            print(padding, '{} {} {}'.format(self.term, self.comp, self.rval), sep='\t')
        elif self.type == 'loop':
            print(padding, 'For value {} in range [{},{}]: '.format(self.loopvar, self.range[0], self.range[1]), sep='\t', end='')
            
            if isinstance(self.term, str):
                if self.comp and self.rval:
                    print('{} {} {}'.format(self.term, self.comp, self.rval))
                else:
                    print(self.term)
            else:
                print('the following constraints holds:')
                for t in self.term:
                    t._print(level+1)
        elif self.type == 'and' or self.type == 'or':
            print(padding, 'the logical {} of the following constraints holds:'.format(self.type), sep='\t')
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

        reserved = ('x', 'y', 'And', 'Or', 'If')
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
        
        if 'comment' in obj:
            self.comment = obj['comment']
        else:
            self.comment = None



class ProblemModel:
    def __init__(self, file_path=None, encoding='utf-8', verbose=False):
        self.json = None
        self.problem_text = None
        self.objective = None
        self.variable = None
        self.constraint = None
        self.input = []
        self.param = []
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
            Obj = js['input']
            for obj in Obj:
                self.input.append(_Input(obj, self.verbose))
        
        if 'parameter' in js:
            Obj = js['parameter']
            if isinstance(Obj, list):
                for obj in Obj:
                    self.param.append(_Parameter(obj, self.verbose))
            elif isinstance(Obj, dict):
                self.param.append(_Parameter(Obj, self.verbose))
    
    @staticmethod
    def _get_number(i,val_dict):

        if isinstance(i, int) or isinstance(i, float):
            return i
        elif isinstance(i, str):
            try:
                return eval(i, val_dict)
            except:
                raise Exception('Cannot find value {}'.format(i))
        else:
            raise Exception('Illegal type: {}'.format(type(i)))
    
    @staticmethod
    def _parse_constraint(con, _val, x, y, opt, retList=None, verbose=False, specs=None):
        
        _val['x'] = x
        _val['y'] = y
        _val['Or'] = Or
        _val['And'] = And
        _val['If'] = If
        
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
                specs['n_unit'] += 1
            else:
                term = '[{} for {} in range({},{}+1)]'.format(
                    con.term, con.loopvar, con.range[0], con.range[1])
            term = eval(term, _val)
            if con.type == 'sum':
                specs['n_unit'] += len(term)
                term = Sum(term)
            elif con.type == 'product':
                specs['n_unit'] += len(term)
                term = Product(term)
            
            if con.comp!=None and con.rval!=None:
                rval = eval(con.rval, _val) if isinstance(con.rval, str) else con.rval
                final = get_comp(con.comp)(term, rval)
            else:
                final = term
            
            if retList != None:
                retList.append(final)
            else:
                opt.add(final)
                if specs != None:
                    specs['n_constraint'] += 1
                if verbose:
                    print('Adding constraint:', final)
        
        elif con.type == 'loop':
            lbound = ProblemModel._get_number(con.range[0], _val)
            ubound = ProblemModel._get_number(con.range[1], _val)
            
            if con.loopvar in _val:
                raise Exception('Loop variable {} already exists.'.format(con.loopvar))
            
            for i in range(lbound, ubound+1):
                _val[con.loopvar] = i
                if isinstance(con.term, str):
                    term = eval(con.term, _val)
                    specs['n_unit'] += 1

                    if con.comp!=None and con.rval!=None:
                        rval = eval(con.rval, _val) if isinstance(con.rval, str) else con.rval
                        final = get_comp(con.comp)(term, rval)
                    else:
                        final = term
                    
                    if retList != None:
                        retList.append(final)
                    else:
                        opt.add(final)
                        if specs != None:
                            specs['n_constraint'] += 1
                        if verbose:
                            print('Adding constraint:', final)
                else:
                    for cons in con.term:
                        ProblemModel._parse_constraint(cons, _val, x, y, 
                            opt, retList, verbose=verbose, specs=specs)
            
            del _val[con.loopvar]
        
        elif con.type == 'or' or con.type == 'and':
            condList = []
            for cons in con.term:
                ProblemModel._parse_constraint(cons, _val, x, y, 
                    opt, condList, verbose=verbose, specs=specs)
            if specs != None:
                specs['n_constraint'] += len(condList)
            if len(condList) == 1:
                final = condList[0]
            else:
                if con.type == 'or':
                    final = Or(condList)
                else:
                    final = And(condList)
            if retList != None:
                retList.append(final)
                specs['n_constraint'] -= 1
            else:
                opt.add(final)
                if verbose:
                    print('Adding constraint:', final)
        
        else:
            raise Exception('Illegal constraint type: {}'.format(con.type))

    @staticmethod
    def get_article(word):
        if word[0] in ('a','e','i','o','u'):
            return 'an'
        else:
            return 'a'

    def _input(self, input_=None):
        input_dict = {}

        inputs = None
        if input_ != None:
            with open(input_, "r") as f:
                inputs = f.readlines()

        for idx,i in enumerate(self.input):
            if i.name in input_dict:
                raise Exception('Duplicate input name: {}'.format(i.name))

            if i.type in ('int', 'real'):
                if inputs == None:
                    print('Input {}, {} {} number{}: '.format(
                    i.name, ProblemModel.get_article(i.type), i.type,
                    ', '+i.comment if i.comment else ''), end='')
                tp = int if i.type == 'int' else float
                try:
                    if inputs != None:
                        input_dict[i.name] = tp(inputs[idx])
                    else:
                        input_dict[i.name] = tp(input())
                except ValueError:
                    raise Exception('Illegal input')
                
            
            elif i.type in ('intarray', 'realarray'):
                tp = int if i.type == 'intarray' else float

                length = ProblemModel._get_number(i.length, input_dict)
                
                if inputs == None:
                    print('Input {}, {} {} of length {}{}: '.format(
                    i.name, ProblemModel.get_article(i.type), i.type, length,
                    ', '+i.comment if i.comment else ''), end='')
                try:
                    if inputs != None:
                        input_dict[i.name] = [tp(x) for x in inputs[idx].split()]
                    else:
                        input_dict[i.name] = [tp(v) for v in input().split()]
                except ValueError:
                    raise Exception('Illegal input')
                
                if len(input_dict[i.name]) != length:
                    raise Exception('Input length mismatch: {} != {}'.format(len(input_dict[i.name]), length)) 
            
            else:
                raise Exception('Illegal input type: {}'.format(i.type))
        
        return input_dict
    
    
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
        
        print('This problem has {} parameters:'.format(len(self.param)))
        for i,c in enumerate(self.param):
            print('Parameter {}:'.format(i+1))
            print('\tName: {}'.format(c.name))
            print('\tType: {}'.format(c.type))
            print('\tDefault value: {}'.format(c.value))
            print('\tBound: {}'.format(c.range))
    

    def solve(self, verbose = False, nosolve=False, input_=None):
        # first, handle input
        value_dict = self._input(input_=input_)
        # then, add parameter
        for p in self.param:
            if p.name in value_dict:
                raise Exception('Name {} already exists.'.format(p.name))
            value_dict[p.name] = p.value
        

        # declare optimizer, variable x, and goal y
        opt = Solver() if self.objective.goal == 'exist' else Optimize()

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
        specs = {'n_constraint': 0, 'n_unit': 0}
        now = time.time()
        for con in self.constraint:
            ProblemModel._parse_constraint(con, value_dict, x, y, opt, 
                retList=None, verbose=verbose, specs=specs)
        specs['time_constraint'] = time.time() - now

        if nosolve:
            specs['time_solve'] = None
            return None, None, specs

        result, model = None, None

        now = time.time()        
        if self.objective.goal == 'exist':
            if opt.check() != sat:
                result, model = False, None
            else:
                result, model = True, opt.model()
        else:
            h = opt.maximize(y) if self.objective.goal == 'max' else opt.minimize(y)
            if opt.check() != sat:
                result, model = False, None
            if self.objective.goal == 'max':
                result, model = opt.upper(h), opt.model()
            else:
                result, model = opt.lower(h), opt.model()
        
        specs['time_solve'] = time.time() - now
        return result, model, specs
    
        
    def mutate(self, mode=None):
        modes = ('objective', 'constraint', 'parameter')
        if mode==None:
            mode = random.choice(modes)
        elif mode not in modes:
            raise Exception('Illegal mode: {}'.format(mode))
        
        lang = _words[self.lang]
        res = copy.deepcopy(self)
        
        if mode=='objective':
            obj = self.objective
            before, after = self.problem_text[:obj.index[0]-1], self.problem_text[obj.index[1]:]
            target = 'min' if obj.goal == 'max' else 'max'
            
            res.problem_text = before + lang[target] + after
            res.objective.goal = target
            res.objective.index = [len(before)+1, len(before)+len(lang[target])]

        elif mode=='constraint':
            cons = list(filter(lambda x: x.index!=None, self.constraint))
            if len(cons) == 0:
                raise Exception('No constraints to mutate')
            con = random.choice(cons)
        
        elif mode == 'parameter':
            if len(self.param) == 0:
                raise Exception('No parameters to mutate')
            pIndex = random.randint(0, len(self.param)-1)
            param = self.param[pIndex]

            if param.range[1]-param.range[0] <= 0:
                raise Exception('Range too narrow: {}'.format(param.range))
            
            newval = random.randint(param.range[0], param.range[1])
            while newval==param.value:
                newval = random.randint(param.range[0], param.range[1])
            
            before, after = self.problem_text[:param.index[0]-1], self.problem_text[param.index[1]:]
            res.problem_text = before + str(newval) + after
            res.param[pIndex].value = newval
            res.param[pIndex].index[1] = param.index[0]+len(str(newval))-1

        else:
            pass

        return res