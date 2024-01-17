"""Utilities to go between XYZ files and SMILES strings"""
from threading import Lock

from rdkit.Chem import rdDetermineBonds, AllChem
from rdkit import Chem
import numpy as np

from mofa.utils.src import const

_generate_lock = Lock()


def xyz_to_mol(xyz: str) -> Chem.Mol:
    """Generate a RDKit Mol object with bonds from an XYZ string

    Args:
        xyz: XYZ string to parse
    Returns:
        RDKit mol object
    """

    mol = Chem.MolFromXYZBlock(xyz)
    rdDetermineBonds.DetermineConnectivity(mol)
    rdDetermineBonds.DetermineBondOrders(mol)
    return mol


def xyz_to_smiles(xyz: str) -> str:
    """Generate a SMILES string from an XYZ string

    Args:
        xyz: XYZ string to parse
    Returns:
        SMILES string
    """

    mol = xyz_to_mol(xyz)
    return Chem.MolToSmiles(mol)


def smiles_to_xyz(smiles: str) -> str:
    """Generate an XYZ-format structure from a SMILES string

    Uses RDKit's 3D coordinate generation

    Args:
        smiles: SMILES string from which to generate molecule
    Returns:
        XYZ-format geometry
    """

    # From: https://github.com/exalearn/ExaMol/blob/main/examol/simulate/initialize.py
    with _generate_lock:
        # Generate 3D coordinates for the molecule
        mol = Chem.MolFromSmiles(smiles)
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=1)
        AllChem.MMFFOptimizeMolecule(mol)

        # Save the conformer to an XYZ file
        xyz = Chem.MolToXYZBlock(mol)
        return xyz


def unsaturated_xyz_to_mol(xyz: str) -> Chem.Mol:
    """"""

    # First determine connectivity given 3D coordinates
    mol: Chem.Mol = Chem.MolFromXYZBlock(xyz)
    rdDetermineBonds.DetermineConnectivity(mol)
    conformer: Chem.Conformer = mol.GetConformer(0)
    positions = conformer.GetPositions()

    # Based on that connectivity, infer the bond order
    for bond in mol.GetBonds():
        bond: Chem.Bond = bond

        # Get the distance between atoms
        atom_1, atom_2 = bond.GetBeginAtom(), bond.GetEndAtom()
        atom_1: Chem.Atom = atom_1
        distance = np.linalg.norm(
            positions[atom_1.GetIdx(), :] - positions[atom_2.GetIdx(), :]
        ) * 100  # Distance in pm, to match with the database

        # Infer if the bond order is larger than single
        # Adapted from "utils/src/molecule_builder.py
        type_1, type_2 = atom_1.GetSymbol(), atom_2.GetSymbol()
        margins = const.MARGINS_EDM
        bond_type = Chem.BondType.SINGLE

        if type_1 in const.BONDS_2 and type_2 in const.BONDS_2[type_1]:
            thr_bond2 = const.BONDS_2[type_1][type_2] + margins[1]
            if distance < thr_bond2:
                bond_type = Chem.BondType.DOUBLE
                if type_1 in const.BONDS_3 and type_2 in const.BONDS_3[type_1]:
                    thr_bond3 = const.BONDS_3[type_1][type_2] + margins[2]
                    if distance < thr_bond3:
                        bond_type = Chem.BondType.TRIPLE
        bond.SetBondType(bond_type)

    # Add hydrogens to the molecule
    mol.UpdatePropertyCache()  # Detects the valency
    Chem.AddHs(mol, explicitOnly=True, addCoords=True)

    # TODO (wardlt): Generate positions for the hydrogen atoms, probably by just re-generating the whole conformer

    return mol
