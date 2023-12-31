# sygus parser constants
SYNTH_FUN = "synth-fun"
DEF_FUN = "define-fun"
NT_STRING = "ntString String"
NT_INT = "ntInt Int"
CONSTRAINT = "constraint"
STRING_VAR = "string"
INTEGER_VAR = "integer"
EMPTY_STRING = '""'


class StrParser:
    """
    Returns:
            str_var: variables to represent input string data
            str_literals: string constants
            int_var: variables to represent input int data
            int_literals: integer literals
            input: input values (for str_var or int_var)
            output: output string database
    """

    def __init__(self, filename):
        self.str_var = []
        self.str_literals = []
        self.int_var = []
        self.int_literals = []
        self.input = []
        self.output = []
        self.problem = filename
        self.test_cases = []
        self.nt_ops = []

    def reset(self):
        self.str_var = []
        self.str_literals = []
        self.int_var = []
        self.int_literals = []
        self.input = []
        self.output = []
        self.test_cases = []
        self.nt_ops = []

    def parse_str_literals(self, line):
        indices = [index for index, character in enumerate(line) if character == '"']
        for i in range(0, len(indices), 2):
            self.str_literals.append(line[indices[i] + 1 : indices[i + 1]])

    def parse_vars(self, line, var_type):
        temp = line.strip().split(" ")
        bank = []
        if len(temp) == 1 and temp[0] == "":
            bank = []
        else:
            bank = temp

        if var_type == STRING_VAR:
            self.str_var = bank
        elif var_type == INTEGER_VAR:
            self.int_var = bank

    def parse_int_literals(self, line):
        temp = line.strip().split(" ")
        if len(temp) == 1 and temp[0] == "":
            self.int_literals = []
        else:
            self.int_literals = [int(integer) for integer in temp]

    def parse_io_pair(self, line):
        # (constraint (= (f "1/17/16-1/18/17" 1) "1/17/16")) ==> "1/17/16-1/18/17" 1) "1/17/16"))
        io = line.split("(f")[1].strip()

        # "1/17/16-1/18/17" 1) "1/17/16")) ==> ["1/17/16-1/18/17" 1, "1/17/16", ..]
        io_splitted = io.split(")", 1)

        inp = io_splitted[0].strip()

        out = io_splitted[1].strip()[:-2]

        inp = self.process_input(inp)
        out = self.process_output(out)

        self.input += [inp]
        self.output.append(out)

    def process_input(self, p_input):

        if '"' in p_input:
            if '""' in p_input:
                p_input = p_input.replace('""', '"empty_string_here_sa"')
            inp = [i.strip() for i in p_input.split('"')]

        else:
            inp = [i.strip() for i in p_input.split(" ")]

        inp = list(filter(lambda x: x != "", inp))
        inp = [i.replace("empty_string_here_sa", "") for i in inp]

        inp = list(map(self.parse_type, inp))
        temp = []
        count = 0
        for _ in range(len(self.str_var)):
            temp.append(str(inp[count]))
            count += 1
        for _ in range(len(self.int_var)):
            temp.append(int(inp[count]))
            count += 1
        return temp

    def parse_type(self, value):
        try:
            value = int(value)
        except:
            pass
        return value

    def process_output(self, output):
        if '"' in output:
            return output.replace('"', "")
        try:
            output = int(output)
        except:
            if "true" in output:
                output = True
            elif "false" in output:
                output = False
        return output

    def read(self, filename):
        # self.reset()
        f = open(filename, "r")

        lines = f.readlines()
        for step, line in enumerate(lines):

            if NT_STRING in line:
                str_var = lines[step + 1].strip()
                str_literals = lines[step + 2].strip()

                self.parse_vars(str_var, STRING_VAR)
                self.parse_str_literals(str_literals)

            if NT_INT in line:
                int_var = lines[step + 1].strip()
                int_literals = lines[step + 2].strip()

                self.parse_vars(int_var, INTEGER_VAR)
                self.parse_int_literals(int_literals)

            if CONSTRAINT in line:
                io_pair = line.strip()
                self.parse_io_pair(io_pair)

        f.close()

    def transform_outputs(self):
        test_cases = []
        for index, input_value in enumerate(self.input):
            test_case = {}
            count = 0
            for v in self.str_var:
                test_case[v] = input_value[count]
                count += 1

            for v in self.int_var:
                test_case[v] = input_value[count]
                count += 1

            test_case["out"] = self.output[index]

            test_cases.append(test_case)

        self.test_cases = test_cases

    def get_attrs(self):

        self.transform_outputs()
        return [
            self.str_var,
            self.str_literals,
            self.int_var,
            self.int_literals,
            self.test_cases,
            self.problem,
        ]

    def parse(self):

        self.read(self.problem)
        # self.problem = self.filename
        return self.get_attrs()


class BvParser:
    """
    Returns:
            bv_var: variables to represent input bv data
            input: input values (for str_var or int_var)
            output: output string database
    """

    def __init__(self, filename):
        self.bv_var = []
        self.input = []
        self.output = []
        self.problem = filename
        self.test_cases = []

    def reset(self):
        self.bv_var = []
        self.input = []
        self.output = []
        self.test_cases = []

    def parse_vars(self, line: str):
        # (synth-fun f ((x (_ BitVec 64))) (_ BitVec 64)
        temp = line.strip().split(" ")[2:]
        # ((x (_ BitVec 64))) (_ BitVec 64)
        if temp[-1].strip("()").isnumeric():
            temp = temp[:-3]
        else:
            temp = temp[:-1]
        # ((x (_ BitVec 64)))
        i = 0
        while i < len(temp):
            var = temp[i].strip("()")
            self.bv_var.append(var)
            i += 1
            if i < len(temp) and temp[i].strip("()") == "_":
                i += 3

    def parse_io_pair(self, line: str):
        # (constraint (= (f "1/17/16-1/18/17" 1) "1/17/16")) ==> "1/17/16-1/18/17" 1) "1/17/16"
        io = line.split("(f")[1].strip(" ()")

        # "1/17/16-1/18/17" 1) "1/17/16")) ==> ["1/17/16-1/18/17" 1, "1/17/16", ..]
        io_splitted = io.split(")", 1)

        inp = io_splitted[0].strip()

        out = io_splitted[1].strip()

        inp = self.process_input(inp)
        out = self.process_output(out)

        self.input += [inp]
        self.output.append(out)

    def process_input(self, p_input: str):

        return [self.process_output(i.strip(" ()")) for i in p_input.split(" ")]

    def process_output(self, output: str):
        if output.startswith("#x"):
            return int(output[2:].strip(), 16)
        if "true" in output:
            return True
        elif "false" in output:
            return False
        return output

    def read(self, filename):
        # self.reset()
        f = open(filename, "r")

        lines = f.readlines()
        for line in lines:

            if SYNTH_FUN in line:
                self.parse_vars(line)

            if CONSTRAINT in line:
                io_pair = line.strip()
                self.parse_io_pair(io_pair)

        f.close()

    def transform_outputs(self):
        test_cases = []
        for index, input_value in enumerate(self.input):
            test_case = {}
            count = 0
            for v in self.bv_var:
                test_case[v] = input_value[count]
                count += 1

            test_case["out"] = self.output[index]

            test_cases.append(test_case)

        self.test_cases = test_cases

    def get_attrs(self):

        self.transform_outputs()
        return [
            self.bv_var,
            self.test_cases,
            self.problem,
        ]

    def parse(self):

        self.read(self.problem)
        # self.problem = self.filename
        return self.get_attrs()


class HackerDelightParser:
    """
    Returns:
            bv_var: variables to represent input bv data
            input: input values (for str_var or int_var)
            output: output string database
    """

    def __init__(self, filename):
        self.bv_var = []
        self.dst = ""
        self.problem = filename
        self.solution = ""
        self.constants = []

    def str2type(self, s: str) -> str:
        if s == "BitVec":
            return "bv"
        return "bool"

    def parse_vars(self, line: str):
        # (synth-fun f ((x (_ BitVec 64))) (_ BitVec 64)
        temp = line.strip().split(" ")[2:]
        temp = [x.strip("()") for x in temp]
        temp = [x for x in temp if len(x) > 0 and x != "64"]
        self.dst = self.str2type(temp.pop(-1))

        # ((x (_ BitVec 64)))
        i = 0
        while i < len(temp):
            var = temp[i]
            self.bv_var.append(var)
            assert self.str2type(temp[i + 1]) == "bv"
            i += 2

    def parse_solution(self, line: str):
        elems = line.split(" ")[2:]
        elems = elems[3 * len(self.bv_var) :]
        if self.dst == "bv":
            elems = elems[2:]
        else:
            elems = elems[1:]
        for elem in elems:
            if elem.startswith("#x"):
                self.constants.append(elem.strip("() "))
        self.solution = " ".join(elems)
        self.solution = self.solution[:-1]
        for i, name in enumerate(self.bv_var):
            self.solution = self.solution.replace(f" {name}", f" var{i}")
        # print("sol:", self.solution)

    def count_lvl(self, line: str) -> int:
        return line.count("(") - line.count(")")

    def read(self, filename):
        # self.reset()
        f = open(filename, "r")

        lines = f.readlines()
        level = 0
        for line in lines:

            if SYNTH_FUN in line:
                self.parse_vars(line)

            if level > 0:
                level += self.count_lvl(line)
                self.solution += " " + line.strip()

            if DEF_FUN in line:
                self.solution = line.strip()
                level = self.count_lvl(line)

        f.close()

    def get_attrs(self):
        self.parse_solution(self.solution)

        return [
            self.bv_var,
            self.solution,
            self.problem,
        ]

    def parse(self):

        self.read(self.problem)
        # self.problem = self.filename
        return self.get_attrs()