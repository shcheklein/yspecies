"""
ExpressionDataset and helper classes

Classes:
    ExpressionDataset
    GenesIndexes
    SamplesIndexes
"""

from pathlib import Path
from typing import Callable
from typing import List

import pandas as pd


class ExpressionDataset:

    @staticmethod
    def load(name: str,
             expressions_path: Path,
             samples_path: Path,
             species_path: Path = None,
             genes_path: Path = None,
             genes_meta_path: Path = None,
             sep="\t",
             validate: bool = True):
        expressions =  pd.read_csv(expressions_path, sep=sep,  index_col="run")
        samples = pd.read_csv(samples_path, sep=sep,  index_col="run")
        species = None if species_path is None else pd.read_csv(species_path, sep=sep, index_col="species")
        genes = pd.read_csv(genes_path, sep=sep, index_col="Homo_sapiens")
        genes_meta = None if genes_meta_path is None else pd.read_csv(genes_meta_path, sep=sep, index_col="gene") #species	gene	symbol
        return ExpressionDataset(name, expressions, samples, species, genes, genes_meta, validate=validate)

    @staticmethod
    def from_folder(folder: Path,
             expressions_name: str = "expressions.tsv",
             samples_name: str = "samples.tsv",
             species_name: str = "species.tsv",
             genes_name: str = "genes.tsv",
             genes_meta_name: str = "genes_meta.tsv",
             sep="\t",
             validate: bool = True
             ):
        name = folder.name
        genes_meta_path = folder / genes_meta_name if (folder / genes_meta_name).exists() else None
        species_path = folder / species_name if (folder / species_name).exists() else None
        return ExpressionDataset.load(name,
                                      folder / expressions_name,
                                      folder / samples_name,
                                      species_path,
                                      folder / genes_name,
                                      genes_meta_path,
                                      sep,
                                      validate)

    def __init__(self,
                 name: str,
                 expressions: pd.DataFrame,
                 samples: pd.DataFrame,
                 species: pd.DataFrame = None, #additional species info
                 genes: pd.DataFrame = None,
                 genes_meta: pd.DataFrame = None, #for gene symbols and other useful info
                 validate: bool = True  #validates shapes of expressions, genes and samples
                 ):

        self.name = name
        self.expressions = expressions
        self.genes = genes
        self.samples = samples
        self.species = species
        self.genes_meta = genes_meta
        if validate:
            self.check_rep_inv()

    def has_gene_info(self):
        return self.genes_meta is not None

    def has_species_info(self):
        return self.species is not None

    @property
    def by_genes(self):
        return GenesIndexes(self)

    @property
    def by_samples(self):
        return SamplesIndexes(self)

    def __len__(self):
        return self.expressions.shape[0]

    def get_label(self, label: str) -> pd.DataFrame:
        if label in self.samples.columns.to_list():
            return self.samples[[label]]
        elif (self.species is not None) and label in self.species.columns.to_list():
            return self.species[[label]]
        elif label in self.expressions.columns.to_list():
            return self.expressions[[label]]
        elif (self.genes_meta is not None) and label in self.genes_meta.columns.to_list():
            return self.genes_meta[[label]]
        else:
            assert label in self.genes.columns.to_list(), f"cannot find label {label} anywhere!"

    @property
    def extended_expressions(self):
        assert self.has_gene_info(), "Should have additional gene info"
        pass


    def extended_samples(self, samples_columns: List[str] = None, species_columns: List[str] = None):
        '''
        Samples that also inclode species info
        :return:
        '''
        assert self.has_species_info(), "to get extended samples information there should be species info"
        if samples_columns is None:
            smp = self.samples.columns.to_list()
        elif "species" in samples_columns:
            smp = samples_columns
        else:
            smp = samples_columns + ["species"]
        samples = self.samples if samples_columns is None else self.samples[smp]
        species = self.species if species_columns is None else self.species[species_columns]
        return samples.merge(species, left_on="species", right_index=True)
        # return result if "species" in samples_columns else result.drop("species")


    def check_rep_inv(self):
        """
        Checks the class representation invariant.
            - rownames in data == rownames in samples_meta
            - colnames in data == rownames in features_meta

        Raises: AssertionError when violated.
        """
        assert (self.expressions.index == self.samples.index).all, ""
        "Data dataframe and samples_meta are incompatible."
        assert (self.expressions.columns == self.genes.index).all, ""
        "Data dataframe and features_meta are incompatible."



    def copy(self): #TODO copy-meta (if exists)
        return ExpressionDataset(self.name, self.expressions.copy(),
                                 self.genes.copy(),
                                 self.samples.copy())

    def __getitem__(self, items: tuple or List[str] or str):
        """
        :param items:
        :return: dataset[genes, samples] or dataset.by_genes[genes] if samples not specified
        """
        if type(items) == tuple and type(items[1]) != slice:
            ensembl_ids = [items[0]] if type(items[0]) == str else items[0]
            runs = [items[1]] if type(items[1]) == str else items[1]
            upd_genes = self.genes.loc[ensembl_ids]
            upd_samples = self.samples.loc[runs]
            upd_expressions = self.expressions.loc[runs][ensembl_ids]
            return ExpressionDataset(self.name, upd_expressions, upd_genes, upd_samples)
        elif type(items) == tuple and type(items[0]) == slice:
            return self.by_samples[items[1]]
        else:
            return self.by_genes[items]

    @property
    def shape(self):
        return [self.expressions, self.genes, self.samples]

    def _repr_html_(self):
        gs = str(None) if self.genes_meta is None else str(self.genes_meta.shape)
        ss = str(None) if self.species is None else str(self.species.shape)
        return f"<table border='2'>" \
               f"<caption>{self.name}<caption>" \
               f"<tr><th>expressions</th><th>genes</th><th>species</th><th>samples</th><th>Genes Metadata</th><th>Species Metadata</th></tr>" \
               f"<tr><td>{str(self.expressions.shape)}</td><td>{str(self.genes.shape[0])}</td><td>{str(self.genes.shape[1])}</td><td>{str(self.samples.shape[0])}</td><td>{gs}</td><td>{ss}</td></tr>" \
               f"</table>"

    def write(self, folder: Path or str,
              expressions_name: str = "expressions.tsv",
              samples_name: str = "samples.tsv",
              species_name: str = "species.tsv",
              genes_name: str = "genes.tsv",
              genes_meta_name: str = "genes_meta.tsv",
              name_as_folder: bool = True,
              sep: str = "\t"):
        d: Path = folder if type(folder) == Path else Path(folder)
        folder: Path = d / self.name if name_as_folder else d
        folder.mkdir(parents=True, exist_ok=True) #create if not exist
        self.expressions.to_csv(folder / expressions_name, sep=sep, index = True)
        self.genes.to_csv(folder / genes_name, sep = sep, index = True)
        self.samples.to_csv(folder / samples_name, sep=sep, index = True)
        if self.genes_meta is not None:
            self.genes_meta.to_csv(folder / genes_meta_name, sep=sep, index=True)
        if self.species is not None:
            self.species.to_csv(folder / species_name, sep=sep, index=True)
        print(f"written {self.name} dataset content to {str(folder)}")
        return folder

class SamplesIndexes:
    """
    Representes by_samples indexer, i.d. dataset.by_samples[[gene_ids]]
    """
    def __init__(self, dataset):
        self.dataset = dataset

    def collect(self, filter_fun: Callable[[pd.DataFrame], pd.DataFrame]) -> ExpressionDataset:
        upd_samples: pd.DataFrame = filter_fun(self.dataset.samples)
        runs = upd_samples.index.tolist()
        upd_expressions = self.dataset.expressions.loc[runs]
        return ExpressionDataset(self.dataset.name, upd_expressions, self.dataset.genes, upd_samples)


    def filter(self, filter_fun: Callable[[pd.DataFrame], pd.DataFrame]) -> ExpressionDataset:
        return self.collect(lambda df: self.dataset.samples[filter_fun(df)])


    def __getitem__(self, item) -> ExpressionDataset:
        items = [item] if type(item) == str else item
        upd_samples = self.dataset.samples.loc[items]
        upd_expressions = self.dataset.expressions.loc[items]
        return ExpressionDataset(self.dataset.name, upd_expressions, self.dataset.genes, upd_samples)


    def _repr_html_(self):
        return f"<table border='2'>" \
               f"<caption>{self.dataset.name} samples view<caption>" \
               f"<tr><th>Samples</th>" \
               f"<tr><td>{str(self.dataset.samples.shape[0])}</td></tr>" \
               f"</table>"

class GenesIndexes:
    """
    Representes by_genes indexer, i.d. dataset.by_genes[[gene_ids]]
    """
    def __init__(self, dataset: ExpressionDataset):
        self.dataset = dataset

    def __getitem__(self, item) -> ExpressionDataset:
        items = [item] if type(item) == str else item
        upd_genes = self.dataset.genes.loc[items]
        upd_expressions = self.dataset.expressions[items]
        return ExpressionDataset(self.dataset.name, upd_expressions, upd_genes, self.dataset.samples)


    def _repr_html_(self):
        return f"<table border='2'>" \
               f"<caption>{self.dataset.name} Genes view<caption>" \
               f"<tr><th>Genes</th><th>Species</th><th>Species</th></tr>" \
               f"<tr><td>{str(self.dataset.genes.shape[0])}</td><td>{str(self.dataset.genes.shape[1])}</td></tr>" \
               f"</table>"

    def collect(self, filter_fun: Callable[[pd.DataFrame], pd.DataFrame]) -> ExpressionDataset:
        upd_genes: pd.DataFrame = filter_fun(self.dataset.genes)
        genes = upd_genes.index.tolist()
        upd_expressions = self.dataset.expressions[genes]
        return ExpressionDataset(self.dataset.name, upd_expressions, upd_genes, self.dataset.samples)

    def filter(self, filter_fun: Callable[[pd.DataFrame], pd.DataFrame]) -> ExpressionDataset:
        return self.collect(lambda df: self.dataset.genes[filter_fun(df)])
