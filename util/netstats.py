"""
Functions used to process VTR '.net' output files.
"""

from lxml.etree import Element
from typing import Callable

def check_element_not_open(elem: Element) -> bool:
    """
    Check that @name != 'open'.
    """
    return elem.attrib['name'] != 'open'

def check_element_is_wire(elem: Element) -> bool:
    """
    Check that @mode == 'wire'.
    """
    if not check_element_not_open(elem):
        return False

    return elem.attrib['mode'] == 'wire'

def find_all_block_instances(root: Element, instance_name: str) -> list[Element]:
    """
    Finds all with './/block[@instance="<instance_name>"]'.
    """
    return root.findall(f'.//block[@instance="{instance_name}"]')

def get_valid_child_block_instance(block: Element, instance_name: str, 
    check_valid: Callable[[Element], bool] = check_element_not_open
) -> Element:
    """
    Returns the child Element if the child instance is valid, else None:
    uses 'block[@instance="<instance_name>"]'.

    Required arguments:
    * block:Element, parent Element.
    * instance_name:str, instance name.

    Optional arguments:
    * check_valid: (Element) -> bool, used to check if the found child is valid. Default: check for @name != 'open'
    """
    child = block.find(f'block[@instance="{instance_name}"]')
    if child is not None and check_valid(child):
        return child
    
    return None


def get_valid_child_block_mode(block: Element, mode_name: str, 
    check_valid: Callable[[Element], bool] = check_element_not_open
) -> Element:
    """
    Returns the child Element if the child mode is valid, else None:
    uses 'block[@mode="<mode_name>"]'.

    Required arguments:
    * block:Element, parent Element.
    * mode_name:str, mode name.

    Optional arguments:
    * check_valid: (Element) -> bool, used to check if the found child is valid. Default: check for @name != 'open'
    """
    child = block.find(f'block[@mode="{mode_name}"]')
    if child is not None and check_valid(child):
        return child
    
    return None
