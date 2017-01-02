# coding=utf-8
try:
    import cPickle
except ImportError:
    import pickle as cPickle
import csv

import numpy as np
import pandas as pd
from Bio import SeqIO

from evolutron.tools.seq_tools import aa_map, nt_map, aa2hot, SecS2hot_8cat, SecS2hot_3cat, aa2codon, hot2aa


############################
# -------- Classes ------- #
############################
class Protein(object):
    def __init__(self, name, organism, aa_seq, nt_seq):
        self.name = name
        self.aa_seq = aa_seq
        self.nt_seq = nt_seq
        self.aa = str(self.aa_seq)
        self.nt = str(self.nt_seq)
        self.aa_num = len(aa_seq)
        if nt_seq:
            self.nt_num = len(nt_seq)
        else:
            self.nt_num = None
        self.org = organism


class ZincFinger(Protein):
    def __init__(self, name, organism, aa_seq, nt_seq, pwm):
        """

        :type rec_site: Nucleotide sequence of the recognition site
        """
        Protein.__init__(self, name, organism, aa_seq, nt_seq)
        self.pwm = pwm
        self.rec_site = np.power(np.ones_like(pwm) * 2.0, pwm) * .25

    def __str__(self):
        return '{x.name} {x.nt_num} nt {x.aa_num} aa'.format(x=self)


##############################
# -------- Functions ------- #
##############################

def b1h(padded=False, min_aa=None, max_aa=None):
    filename = 'datasets/B1H.motifs.csv'

    data = csv.DictReader(open(filename, 'r'))

    znf = []

    for d in data:
        r_s = np.zeros((4, 4))
        for i, nt in enumerate(['A', 'C', 'G', 'T']):
            for pos in range(4):
                r_s[i, pos] = d[nt + str(pos + 1)]
        znf.append(ZincFinger(d['Gene/Range'], d['Organism'], d['ZF protein sequence'], None, r_s))

    aa_list = [zf.aa for zf in znf if zf.aa.find('X') == -1]

    if padded:
        if not max_aa:
            max_aa = max(map(len, aa_list))
        x_data = np.zeros((len(aa_list), 20, max_aa), dtype=np.float32)
        for i, aa_seq in enumerate(aa_list):
            for j, aa in enumerate(aa_seq):
                x_data[i, int(aa_map[aa]), j] = 1
    else:
        x_data = [np.zeros((20, max(len(aa_seq), min_aa)), dtype=np.float32) for aa_seq in aa_list]

        for ind, aa_seq in enumerate(aa_list):
            for j, aa in enumerate(aa_seq):
                x_data[ind][int(aa_map[aa]), j] = 1

    y_data = np.asarray([zf.rec_site.reshape(16) for zf in znf if zf.aa.find('X') == -1])

    dataset = x_data, y_data

    return dataset


def m6a(padded=False, min_aa=None, max_aa=None, probe='both'):
    """
        This module parses data from m6a proto-array for Evolutron
    """
    infile = 'datasets/m6a.csv'
    data = csv.DictReader(open(infile, 'r'))
    data = list(data)

    empty = [d for d in data if len(d['AA']) <= 4]

    unknown = [d for d in data if not d['AA'].find('U') == -1 or not d['AA'].find('X') == -1]

    passed = [d for d in data if len(d['AA']) > 5 and d['AA'].find('U') == -1 and d['AA'].find('X') == -1]

    probe1 = [p for p in passed[::2]]
    probe2 = [p for p in passed[1::2]]

    if probe == '1':
        datapoints = probe1
    elif probe == '2':
        datapoints = probe2
    else:
        datapoints = passed

    del probe1
    del probe2
    del passed

    aa_list = []
    conc_list = []
    for d in datapoints:
        aa_list.append(eval(d['AA'])[0][0])
        conc_list.append([float(d['Array_60531']), float(d['Array_60690']), float(d['mean'])])

    if padded:
        if not max_aa:
            max_aa = max(map(len, aa_list))
        x_data = np.zeros((len(aa_list), 20, max_aa), dtype=np.float32)
        for i, aa_seq in enumerate(aa_list):
            for j, aa in enumerate(aa_seq):
                if j == min_aa:
                    break
                x_data[i, int(aa_map[aa]), j] = 1
    else:
        x_data = [np.zeros((20, max(len(aa_seq), min_aa)), dtype=np.float32) for aa_seq in aa_list]

        for ind, aa_seq in enumerate(aa_list):
            for j, aa in enumerate(aa_seq):
                x_data[ind][int(aa_map[aa]), j] = 1

    y_data = np.asarray(conc_list)

    dataset = x_data, y_data

    return dataset


def type2p_code(description):
    """
        This module parses data from REBASE and transforms them for Evolutron
    """
    # Read fasta input
    rec_site = description.split(' ')[-1]

    code = np.zeros((len(rec_site), 4), dtype=np.float32)
    for j, nt in enumerate(rec_site):
        code[j, :] = np.asarray(nt_map[nt])

    return code.flatten()


def fasta_parser(filename, codes=False):
    """
        This module parses data from FASTA files and transforms them to Evolutron format.
    """

    input_file = open(filename, "rU")

    aa_list = []
    code_list = []
    for record in SeqIO.parse(input_file, "fasta"):
        aa_list.append(str(record.seq))
        if codes:
            if filename == 'datasets/scop2.fasta':
                code_list.append(record.description.split('|')[-1])
            else:
                code_list.append(type2p_code(record.description))  # TODO: make this work with other codes too

    x_data = list(map(aa2hot, aa_list))

    if codes:
        y_data = code_list
    else:
        y_data = None

    return x_data, y_data


def tab_parser(filename, codes=False, key='fam', nb_aa=20):

    try:
        raw_data = pd.read_hdf(filename.split('.')[0] + '.h5', 'raw_data')
    except FileNotFoundError:
        raw_data = pd.DataFrame.from_csv(filename, sep='\t', header=0)
        raw_data.columns = raw_data.columns.str.strip().str.lower().str.replace(' ', '_')
        raw_data['fam'] = raw_data['protein_families'].apply(fam)
        raw_data['sup'] = raw_data['protein_families'].apply(supfam)
        raw_data['sub'] = raw_data['protein_families'].apply(subfam)

        raw_data.to_hdf(filename.split('.')[0] + '.h5', 'raw_data')

    x_data = raw_data.sequence.apply(lambda x: aa2hot(x, nb_aa)).tolist()

    if codes:
        pf = raw_data[key].astype('category')
        raw_data['codes'] = pf.cat.codes
        pos_data = raw_data[raw_data['codes'] > 0]
        y_data = pos_data.codes.tolist()
        y_data = [y + 1 for y in y_data]
        x_data = pos_data.sequence.apply(lambda x: aa2hot(x, nb_aa)).tolist()
    else:
        y_data = None

    return x_data, y_data


def SecS_parser(filename, nb_categories=8, nb_aa=20, dummy_option=None):
    """
        This module parses data from files containing sequence and secondary structure
        and transforms them to Evolutron format.
    """

    input_file = open(filename, "rU")

    aa_list = []
    SecS_list = []
    flag = True
    for record in SeqIO.parse(input_file, "fasta"):
        if flag:
            seq = str(record.seq)
            aa_list.append(seq)

            flag = False
        else:
            sec = str(record.seq)
            SecS_list.append(sec)

            flag = True

    x_data = list(map(lambda x: aa2hot(x, nb_aa), aa_list))
    if nb_categories == 8:
        y_data = list(map(SecS2hot_8cat, SecS_list))
    elif nb_categories == 3:
        y_data = list(map(SecS2hot_3cat, SecS_list))
    else:
        raise TypeError('Number of categories should be 8 or 3')

    return x_data, y_data


def npz_parser(filename, nb_categories=8, pssm=False, codon_table=False,
               extra_features=False, nb_aa=22, dummy_option=None):
    """
        This module parses data from npz files containing sequence and secondary structure
        and transforms them to Evolutron format.
    """

    data = np.load(filename)

    data = np.reshape(data[:], (-1, 700, 57))

    x_data = data[:, :, :nb_aa]

    if pssm:
        x_data = np.concatenate((x_data, data[:, :, 35:35+nb_aa]), axis=-1)
    if extra_features:
        x_data = np.concatenate((x_data, data[:, :, 31:33]), axis=-1)
    if codon_table:
        codons = []
        for i in range(data.shape[0]):
            codons.append(aa2codon(hot2aa(data[i, :, 0:22])))
        x_data = np.concatenate((x_data, codons), axis=-1)

    y_data = data[:, :, 22:30]

    return x_data, y_data


class Handle(object):
    """ Handles names for loading and saving different models.
    """

    def __init__(self,
                 epochs=None,
                 filters=None,
                 filter_length=None,
                 model=None,
                 ftype=None,
                 program=None,
                 data_id=None,
                 conv=None,
                 fc=None,
                 **kwargs):
        self.epochs = epochs
        self.filters = filters
        self.filter_size = filter_length

        self.model = model
        self.ftype = ftype
        self.program = program
        self.dataset = data_id

        self.n_convs = conv
        self.n_fc = fc

        self.filename = str(self).split('/')[-1]

    def __str__(self):
        return '{0}/{1}_{2}_{3}_{4}_{7}_{5}.{6}'.format(self.dataset,
                                                        self.filters,
                                                        self.filter_size,
                                                        self.epochs,
                                                        self.n_convs,
                                                        self.model,
                                                        self.ftype,
                                                        self.n_fc)

    def __repr__(self):
        return '{0}/{1}_{2}_{3}_{4}_{7}_{5}.{6}'.format(self.dataset,
                                                        self.filters,
                                                        self.filter_size,
                                                        self.epochs,
                                                        self.n_convs,
                                                        self.model,
                                                        self.ftype,
                                                        self.n_fc)

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

    @classmethod
    def from_filename(cls, filename):
        try:
            basename, ftype, __ = filename.split('.')
        except ValueError:
            basename, ftype = filename.split('.')
        dataset = basename.split('/')[-2]

        info = basename.split('/')[-1]

        filters, filter_size, epochs, conv, fc = map(eval, info.split('_')[:5])

        model = info.split('_')[-1]

        obj = cls(epochs=epochs, filters=filters, filter_length=filter_size, conv=conv, fc=fc,
                  data_id=dataset, model=model, ftype=ftype)

        return obj


def fam(x):
    dt = str(x).split(',')
    f = [d for d in dt if d.find(' family') >= 0]

    try:
        return f[0]
    except IndexError:
        return "Unassigned"


def supfam(x):
    dt = str(x).split(',')
    f = [d for d in dt if d.find('superfamily') >= 0]

    try:
        return f[0]
    except IndexError:
        return "Unassigned"


def subfam(x):
    dt = str(x).split(',')
    f = [d for d in dt if d.find('subfamily') >= 0]

    try:
        return f[0]
    except IndexError:
        return "Unassigned"
