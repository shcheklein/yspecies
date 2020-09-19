from functools import cached_property

from sklearn.pipeline import Pipeline

from yspecies.config import *
from yspecies.partition import DataPartitioner
from yspecies.partition import PartitionParameters
from yspecies.preprocess import DataExtractor
from yspecies.results import FeatureSummary
from yspecies.selection import CrossValidator, ShapSelector
from yspecies.tuning import MultiObjectiveResults
from yspecies.workflow import TupleWith, Repeat, Collect


@dataclass
class PipelineFactory:
    locations: Locations
    repeats: int = 10
    n_folds: int = 5
    n_hold_out: int = 1

    @cached_property
    def partition_parameters(self):
        return PartitionParameters(self.n_folds, self.n_hold_out, 2,   42)

    def load_study_by_trait(self, trait: str, study_name: str = None):
        path = self.locations.interim.optimization / (trait+".sqlite")
        study_name = f"{trait}_r2_huber_kendall" if study_name is None else study_name
        return self.load_study(path, study_name)

    def load_study(self, path: Path, name: str):
        url = f'sqlite:///' +str(path.absolute())
        print('loading (if exists) study from '+url)
        storage = optuna.storages.RDBStorage(
            url=url
            #engine_kwargs={'check_same_thread': False}
        )
        return optuna.multi_objective.study.create_study(directions=['maximize', 'minimize', 'maximize'], storage=storage, study_name=name, load_if_exists = True)

    def make_partitioning_shap_pipeline(self, trait: str, study_name: str = None):
        study_name = f"{trait}_r2_huber_kendall" if study_name is None else study_name
        study = self.load_study_by_trait(trait, study_name)
        if len(study.get_pareto_front_trials())>0 :
            metrics, params = MultiObjectiveResults.from_study(study).best_metrics_params_r2()
            params["verbose"] = -1
            if "early_stopping_round" not in params:
                params["early_stopping_round"] = 10
        else:
            params = {"bagging_fraction": 0.9522534844058304,
                      "boosting_type": "dart",
                      "objective": "regression",
                      "feature_fraction": 0.42236910941558053,
                      "lambda_l1": 0.020847266580277746,
                      "lambda_l2": 2.8448564854773326,
                      "learning_rate": 0.11484015430016059,
                      "max_depth": 3,
                      "max_leaves": 35,
                      "min_data_in_leaf": 9,
                      "num_iterations": 250,
                      "metrics": ["l1", "l2", "huber"]
                      }
        return Pipeline([
            ("partitioner", DataPartitioner()),
            ('prepare_for_selection', TupleWith(params)),
            ("cross_validation", CrossValidator()),
            ("shap_computation", ShapSelector())
        ]
        )

    def make_shap_pipeline(self, trait: str, study_name: str = None):
        partition_shap_pipe = self.make_partitioning_shap_pipeline(trait, study_name)
        return Pipeline(
            [
                ('extractor', DataExtractor()),
                ('prepare_for_partitioning', TupleWith(self.partition_parameters)), # to extract the data required for ML from the dataset
                ("partition_shap", partition_shap_pipe)
            ]
        )

    def make_repeated_shap_pipeline(self, trait: str, study_name: str = None):
        partition_shap_pipe = self.make_partitioning_shap_pipeline(trait, study_name)
        repeated_cv = Repeat(partition_shap_pipe, self.repeats, lambda x,i: (x[0], replace(x[1], seed=i)))
        return Pipeline(
            [
                ('extractor', DataExtractor()),
                ('prepare_for_partitioning', TupleWith(self.partition_parameters)), # to extract the data required for ML from the dataset
                ("repeated_partition_shap", repeated_cv),
                ("summarize", Collect(fold=lambda results: FeatureSummary(results)))
            ]
        )