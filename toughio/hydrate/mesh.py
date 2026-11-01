from __future__ import annotations

import numpy as np


def set_activity(mesh, mask, flag: str = "I") -> None:
    """
    Set the T+H element activity of cells.

    Parameters
    ----------
    mesh : toughio.Mesh
        Mesh to modify (cell data 'hydrate_activity').
    mask : ArrayLike
        Boolean array, one value per cell.
    flag : str, default 'I'
        '' (active), 'I' (inactive, constant boundary) or 'V01'...'V99' (time-variable
        boundary defined in BOUNDARIES).

    """
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != (mesh.n_cells,):
        raise ValueError("activity mask must have one entry per cell")

    if not (
        flag in {"", "I"} or (len(flag) == 3 and flag[0] == "V" and flag[1:].isdigit())
    ):
        raise ValueError("activity flag must be '', 'I' or 'V01'...'V99'")

    activity = mesh.data.get("hydrate_activity")
    activity = (
        np.full(mesh.n_cells, "", dtype="U3")
        if activity is None
        else np.array(activity, dtype="U3")
    )
    activity[mask] = flag
    mesh.data["hydrate_activity"] = activity


def mesh_parameters(mesh, **kwargs) -> dict:
    """
    Convert a mesh to T+H 'elements' and 'connections' parameters.

    Dirichlet cells keep their true volume and nodal distances and become inactive
    elements (activity 'I') unless an activity is already set.

    Parameters
    ----------
    mesh : toughio.Mesh
        Input mesh. It is not modified.
    **kwargs
        Passed to :meth:`toughio.Mesh.to_tough` (e.g. gravity, assume_orthogonal).

    Returns
    -------
    dict
        Parameters with keys 'elements' and 'connections'.

    """
    dirichlet = np.asarray(mesh.dirichlet, dtype=bool)
    activity = mesh.data.get("hydrate_activity")
    activity = (
        np.full(mesh.n_cells, "", dtype="U3")
        if activity is None
        else np.array(activity, dtype="U3")
    )
    activity[dirichlet & (activity == "")] = "I"

    if dirichlet.any():
        mesh = mesh.copy()
        mesh.dirichlet = np.zeros(mesh.n_cells, dtype=bool)

    parameters = mesh.to_tough(**kwargs)
    flags = dict(zip(mesh.labels, activity))
    for label, element in parameters["elements"].items():
        if flags.get(label):
            element["activity"] = str(flags[label])

    return parameters
