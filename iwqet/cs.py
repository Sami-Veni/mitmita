#
#   Mit'mit'a: CS: what is needed to implement l3 style constraint satisfaction
#   using the lexicon/grammars created.
#
########################################################################
#
#   This file is part of the HLTDI L^3 and PLoGS projects
#   for parsing, generation, translation, and computer-assisted
#   human translation.
#
#   Copyleft 2014, 2015, 2016, 2018 HLTDI and PLoGS <gasser@indiana.edu>
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# =========================================================================

# 2014.04.26
# -- Created
# 2014.05.11
# -- SearchState class created, so that Solver doesn't have to do double-duty.
# 2014.05.15
# -- Search implemented in Solver.
# 2015.07.14
# -- Solver can be passed an explicit evaluator function to assign values to
#    states during best-first search and an explicit variable and value selection
#    function to be used in distribution. Normally one or the other would be
#    used; currently this is the variable selection function.
# 2016.01.17
# -- Random value added to basic value for state evaluation to avoid ties

from .constraint import *
import queue, random

class Solver:
    """A solver for a constraint satisfaction problem."""

    id = 0

    running = 0
    succeeded = 1
    failed = 2
    distributable = 3
    skipped = 4

    def __init__(self, constraints, dstore, name='', evaluator=None,
                 varselect=None,
                 description='', verbosity=0):
        self.constraints = constraints
        # Used in solver's printname
        self.description = description
        # A function that assigns values to states
        self.evaluator = evaluator
        # A function that selects a variable and splits its values, given a list of undetermined variables and a dstore
        self.varselect = varselect
        self.verbosity=verbosity
        self.id = Solver.id
        self.name = name or "({})={}=".format(description, self.id)
        self.init_state = SearchState(solver=self, dstore=dstore,
                                      constraints=constraints,
                                      verbosity=verbosity)
        Solver.id += 1

    def __repr__(self):
        return "Solver{}".format(self.name)

    def generator(self, cutoff=50, initial=None,
                  test_verbosity=False, expand_verbosity=False, tracevar=None):
        '''A generator for solutions. Uses best-first search.'''
        tracevar = tracevar or []
        fringe = queue.PriorityQueue()
        init_state = initial or self.init_state
        fringe.put((init_state.get_value(evaluator=self.evaluator), init_state))
        n = 0
        solutions = []
        ambiguity = False
        while not fringe.empty() and n < cutoff:
            if n > 0 and not ambiguity:
                if expand_verbosity:
                    print("Ambiguity: expanding from best state")
                ambiguity = True
            if (n+1) % 50 == 0 or test_verbosity or expand_verbosity:
                if test_verbosity or expand_verbosity:
                    print()
                print('>>>> SEARCH STATE {} <<<<'.format(n+1))
            if n >= cutoff:
                print('STOPPING AT CUTOFF')
            priority, state = fringe.get()
            if fringe.queue and expand_verbosity:
                print("Estado {}, prioridad {}, estatus: {}, cola: {}".format(state, priority, state.status, fringe.queue))
            # Goal test for this state
            state.run(verbosity=test_verbosity, tracevar=tracevar)
            if state.status == SearchState.succeeded:
                # Return this state
                yield state
            # Expand to next states if distributable
            if state.status == SearchState.distributable:
                score = random.random() / 100.0
                if self.evaluator and n > 0:
                    # Figure the value (priority) of the parent state from scratch AFTER constraint satisfaction has
                    # been run on it.
                    state.get_value(evaluator=self.evaluator, var_value=None)
                for index, (attribs, next_state) in enumerate(self.distribute(state=state, verbosity=expand_verbosity)):
                    # There are exactly two next states: 'a', 'b'
                    if self.evaluator:
                        if index == 0:
                            # The 'a' branch with the promising selected variable and value; evaluate on the basis
                            # of parent state (oldval)
                            val = next_state.get_value(evaluator=self.evaluator, var_value=attribs)
                        else:
                            # The 'b' branch, excluding the promising value from the variable; use parent value
                            val = state.value + random.random() / 100.0
                    else:
                        # If there's no evaluator function, just the order of states returned by distribute.
                        val = score
                        score += 1
                    if expand_verbosity:
                        print(" Próximo estado {}, nivel {}, valor {}".format(next_state, n, val))
                        print("  {} PUTTING new state {} and score {} on fringe of length {}".format(self, next_state, val, fringe.qsize()))
                    fringe.put((val, next_state))
            n += 1
        if test_verbosity or expand_verbosity:
            print()
            print('>>>> HALTED AT SEARCH STATE', n, '<<<<')

    def split_var_values(self, variable, dstore=None, verbosity=0):
        """
        For a selected variable, select a value by calling the value selection
        function, and return two sets of values: the selected value and the
        other values. Assumes variable is a set or int variable.
        """
        undecided = variable.get_undecided(dstore=dstore)
        # Split undecided into two non-empty subsets
        if not undecided:
            print("SOMETHING WRONG; {} HAS NO UNDECIDED VALUES".format(variable))
        elem = Solver.ran_select(undecided)
        return {elem}, undecided - {elem}

    def select_var_values(self, variables, dstore=None, func=None, verbosity=0):
        """Select a undetermined variable to branch on and split its undecided values, ordering
        them by how promising they are. If no func is provided, use the default:
        prefer smaller upper domains and random order."""
        selected = func(variables, dstore) if func else None
        if not selected:
            if verbosity:
                print("Var sel function failed")
            variable = sorted(variables, key=lambda v: len(v.get_upper(dstore=dstore)))[0]
            print("SELECTED")
            variable.pprint(dstore=dstore)
            undecided = variable.get_undecided(dstore=dstore)
            # Split undecided into two non-empty subsets
            if not undecided:
                print("SOMETHING WRONG; {} HAS NO UNDECIDED VALUES".format(variable))
            elem = Solver.ran_select(undecided)
            selected = variable, {elem}, undecided - {elem}
        return selected

    ## Two variable value selection functions.

    @staticmethod
    def ran_select(values):
        """Randomly select a value from a set of values."""
        return random.choice(list(values))

    @staticmethod
    def smallest_select(values):
        """Select smallest value."""
        value_list = list(values)
        value_list.sort()
        return value_list[0]

    def make_constraints(self, variable, subset1=None, subset2=None,
                         dstore=None, verbosity=0):
        """Return a pair of constraints for the selected variable."""
        # There should always be subsets, but for some reason if there isn't...
        if not subset1:
            subset1, subset2 = self.split_var_values(variable, verbosity=verbosity)
        if isinstance(variable, IVar):
            if verbosity:
                print(' making member constraints for {} with values: {}, {}'.format(variable, subset1, subset2))
            return Member(variable, subset1, record=False), Member(variable, subset2, record=False)
        else:
            # For a set Var, add subset1 to the lower bound, subtract subset1
            # from the upper bound
            vlower = variable.get_lower(dstore=dstore)
            vupper = variable.get_upper(dstore=dstore)
            v1 = vlower | subset1
            v2 = vupper - subset1
            if verbosity:
                print(' making superset/subset constraints for {} with values: {}, {}'.format(variable, v1, v2))
            return Superset(variable, v1, record=False), Subset(variable, v2, record=False)

    def distribute(self, state=None, verbosity=0):
        """
        Creates and returns two new states, along with associated essential variables and their values,
        by cloning the dstore with the distributor.
        """
#        if self.status != SearchState.distributable:
#            return []
        state = state or self.init_state
        undet = state.dstore.ess_undet
        ndet = len(undet)
        if verbosity > 1:
            for v in list(undet)[:5]:
                v.pprint(dstore=state.dstore, spaces=2)
            if ndet > 5:
                print('  ...')
        # Select a variable and two disjoint basic constraints on it
        var, values1, values2 = self.select_var_values(undet, dstore=state.dstore,
                                                       func=self.varselect, verbosity=verbosity)
        if verbosity > 1:
            print('Selected variable {} and value sets {},{}'.format(var, values1, values2))
        constraint1, constraint2 = \
           self.make_constraints(var, dstore=state.dstore,
                                 subset1=values1, subset2=values2,
                                 verbosity=verbosity)
#        print("SELECTED CONSTRAINTS FOR VAR")
#        var.pprint(dstore=state.dstore)
#        print('Selected constraints {}, {}'.format(constraint1, constraint2))
        if verbosity > 1:
            print('Distribution constraints: a -- {}, b -- {}'.format(constraint1, constraint2))
        # The constraints of the selected variable (make copies)
        constraints = var.constraints[:]
        # Create the new solvers (states), applying one of the constraints to each
        new_dstore1 = state.dstore.clone(constraint1, name=state.name+'a')
        new_dstore2 = state.dstore.clone(constraint2, name=state.name+'b')
#        # Selected variable is determined in dstore2; try to determine it in dstore1
#        var.determined(dstore=new_dstore1, verbosity=2)
        # Create a new SearchState for each dstore, increasing the depth
        state1 = SearchState(constraints=constraints, dstore=new_dstore1,
                             solver=self,
                             name=state.name+'a', depth=state.depth+1,
                             parent=state, verbosity=verbosity)
        state2 = SearchState(constraints=constraints, dstore=new_dstore2,
                             solver=self,
                             name=state.name+'b', depth=state.depth+1,
                             parent=state, verbosity=verbosity)
        state.children.extend([state1, state2])
        if verbosity:
            print("DISTRIBUTING from {}; variable: {}, state 1: {}, va;ie {}; state 2: {}, value {}".format(state, var, state1, values1, state2, values2))
        return [((var, values1), state1), ((var, values2), state2)]

class SearchState:
    """
    A single state in the search space, created either when the Solver is initialized
    or during distribution.
    """

    # Class variables representing different outcomes for running a SearchState
    running = 0
    succeeded = 1
    failed = 2
    distributable = 3
    skipped = 4

    def __init__(self, solver=None, name='', dstore=None, constraints=None,
                 parent=None, depth=0, verbosity=0):
        self.solver = solver
        self.name = name
        self.dstore = dstore
        self.entailed = []
        self.failed = []
        self.constraints = constraints
        self.parent = parent
        self.children = []
        self.depth = depth
        self.status = SearchState.running
        self.verbosity = verbosity
        self.value = 0.0
#        print("CREATED {}".format(self))
#        self.show_variables()
#        print("CREATED SSTATE with DS {}, UNDET {}".format(dstore, dstore.ess_undet))

    def __repr__(self):
        return "<SS {}/{}>".format(self.name, self.depth)

    def show_variables(self):
        if not self.dstore.undetermined:
            return
        print("STATE {} VARIABLES".format(self))
        for var in self.dstore.undetermined:
            if var.essential:
                var.pprint(dstore=self.dstore)

    def get_value(self, evaluator=None, var_value=None):
        """
        A measure of how promising this state is. Unless there is an explicit
        evaluator for the solver, by default this is how many undetermined
        essential variables there are. (The lower the score, the better.)
        """
        par_value = self.parent.value if self.parent else 0.0
        if evaluator:
            value = evaluator(self.dstore, var_value, par_value)
        else:
            value = len(self.dstore.ess_undet)
        self.value = value
        return value

    def exit(self, result, verbosity=0):
        if result == Constraint.failed:
            return True
        else:
            return self.fixed_point(result, verbosity=verbosity)

    def fixed_point(self, awaken, verbosity=0):
        if verbosity:
            s = "# constraints to awaken: {}, # variables to determine: {}|{}"
            print(s.format(len(awaken), len(self.dstore.ess_undet), len(self.dstore.undetermined)))
        if self.dstore.is_determined():
            # All essential variables are determined
            self.status = SearchState.succeeded
            return True
        elif len(awaken) == 0:
            # More variables to determine; we have to distribute
            self.status = SearchState.distributable
            return True
        # Keep propagating
        return False

    def run(self, verbosity=0, tracevar=[]):
        """Run the constraints until CS fails or a fixed point is reached."""
        if verbosity:
            s = "Running {} with {}|{} undetermined variables, {} constraints"
            print(s.format(self, len(self.dstore.ess_undet), len(self.dstore.undetermined), len(self.constraints)))
        awaken = set(self.constraints)
        it = 0
        while not self.exit(awaken, verbosity=verbosity):
            if verbosity:
                print("Running iteration {}".format(it))
            awaken = self.run_constraints(awaken, verbosity=verbosity, tracevar=tracevar)
            it += 1

    def run_constraints(self, constraints, verbosity=0, tracevar=[]):
        awaken = set()
        all_changed = set()
        failed = set()
        for constraint in constraints:
            state, changed_vars = constraint.run(dstore=self.dstore, verbosity=verbosity, tracevar=tracevar)
            all_changed.update(changed_vars)
            if state == Constraint.entailed:
                # Constraint is entailed; add it to the list of those.
                self.entailed.append(constraint)
                # Delete it from awaken if it's already there
                if constraint in awaken:
                    awaken.remove(constraint)

            if state == Constraint.failed:
                if verbosity:
                    print("FAILED {}".format(constraint))
                return Constraint.failed

            # Check whether any of the changed vars cannot possibly be determined; if so,
            # the constraint fails
            for var in changed_vars:
                try:
                    var.determined(dstore=self.dstore, verbosity=verbosity)
                except VarError:
                    if verbosity:
                        print("{} CAN'T BE DETERMINED, SO {} MUST FAIL".format(var, constraint))
#                    failed.add(constraint)
                    return Constraint.failed

            for var in changed_vars:
                # Add constraints for changed var to awaken unless those constraints are already entailed
                # or failed
                update_cons = {c for c in var.constraints if c not in self.entailed and c not in self.failed}
                if var == tracevar and verbosity:
                    print('Adding {} constraints for changed variable {}'.format(len(update_cons), tracevar))
                awaken.update(update_cons)
        if verbosity > 1:
            print('# changed vars {}'.format(len(all_changed)))
        if verbosity and failed:
            print("{} constraints failed".format(len(failed)))

        return awaken
