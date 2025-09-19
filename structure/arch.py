from structure.util import DynamicallyNamed
from util.search import query_df

import sys, os
import pandas as pd
from lxml.etree import Element

class ArchFactory(DynamicallyNamed):
    """
    {abstract}

    Factory that can generate:
    * an architecture XML file from provided parameters.
    * a COFFE input file.
    
    Can also get a set of MWTA area values from a COFFE archive .csv file.

    With a VTR final '.net' file, an ArchFactory can also return important statistics.
    """

    def get_arch(self, **kwargs) -> str:
        """
        {abstract}
        Refer to concrete ArchFactory class for specification.

        @return "arch.xml" file, in a single string.
        """
        self.raise_unimplemented("get_arch")

    def get_coffe_input_dict(self, **kwargs) -> dict:
        """
        {abstract}
        
        Gets a COFFE input dictionary for the architecture to simulate required area and timing parameters.

        @return COFFE architecture dictionary.
        """
        self.raise_unimplemented("get_coffe_input_dict")

    def get_coffe_archive_values(self,
            search_kwargs: dict[str, any],
            folder: str = 'coffe_archives',
            filename: str | None = None,
            defaults: dict[str, any] | None = None
        ) -> dict[str, any] | None:
        """
        Get COFFE estimates from a COFFE archive .csv file, for given search arguments.

        The COFFE archive file should have columns corresponding to the keys of the search_kwargs argument, and it will return the remaining columns of the FIRST found row as a dictionary.
        
        For example, with the following COFFE archive file:
        a b c d
        0 0 1 2
        0 0 2 4
        0 1 2 3

        and a search_kwargs of a=0, b=0, then this will return { c: 1, d: 2 }.

        Required arguments:
        * search_kwargs:dict[str, any], column: value to search for in the archive file.
        
        Optional arguments:
        * folder:str, specify where the directory the archive file resides in relative to the module file housing the subclass using this function. Default: 'coffe_archives'
        * filename:str | None, specify the archive file "<filename>.csv" to look for in the folder. If None, then it is assumed the .csv file will share the same name as the module file housing the subclass, e.g., "base.py" will have a corresponding "base.csv". Default: None
        * defaults: dict[str, any] | None: specify defaults. Columns that exist in the archive file will override; columns that do not exist are returned as is.

        @return dict[str, any] of the first row found, if any; else defaults, if specified; else None. 
        """
        # Get specified archive file path
        if filename is None:
            filename = self.__module__.split('.')[-1] # take last module name
        archive_path = os.path.join(os.path.dirname(sys.modules[self.__module__].__file__), folder, f"{filename}.csv")

        # Check for existence
        if not os.path.exists(archive_path):
            return defaults
        
        # Read archive
        archive = pd.read_csv(archive_path)

        # Make query
        result = query_df(archive, search_kwargs)
        if result is None:
            return defaults
        
        # return merged result
        return defaults | result.iloc[0][result.columns.drop(search_kwargs.keys())].to_dict()
    
    def should_update_netstats(self, netstats: dict[str, any]) -> bool:
        """
        {abstract}
        Force re-writing of 'netstats.json' whenever this is True. This usually results in slower re-use of existing experiments, since VTR '.net' files will have to be unzipped and re-zipped.
        """
        return False

    def get_netstats(self, root: Element) -> dict[str, any]:
        """
        {abstract}
        Take the root Element of a VTR '.net' file (loaded with lxml.etree), and returns a JSON-serializable dictionary of important statistics.
        """
        return {}