"""
Author: Hwei-Shin Harriman
Altered by: Neel Dhulipala
Original program: https://github.com/occamLab/augmented-reality-tools/blob/plane-visualization/plane-visualization/meshes/meshes.py
Process AR mesh data from Depth Viewer
"""
import json
import numpy as np
import os, sys
from pathlib import Path
import Mesh_pb2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# UUIDs might be different, please check these
IPHONE_UUIDS = {
    "occam": "JdRfgFBxfCUjQA0CTxlJToKQ8eG2"
}

# Read a protobuf file, given a String with the path info
def read_protobuf(filepath):
    f = open(filepath, 'rb')
    m = Mesh_pb2.MeshesProto()
    # Read the mesh and return the output matrix
    m2 = m.FromString(f.read())
    return m2

# Read the raycasts from the metadata JSON file, given String of filepath
def get_raycasts_from_metadata(filepath):
    f = open(filepath)
    # after opening filepath, get it parsed
    metadata = json.load(f)
    return metadata['raycast']

def get_raycasts_from_firebase(iphone, trial_name):
    """
    Find the names of all the paths which include the raycast data requested.

    :param iphone: (str) name of the iPhone where data is stored
    :param trial_name: (str) trial where you want meshes from
    :returns:
    """
    # Count how many files there are in the directory, read protobufs in
    # reverse order
    # NOTE: meshes data has to be downloaded first, which means
    # get_meshes_from_firebase must be called before this function
    num_meshes = len(os.listdir('meshes'))
    raycast_array = []
    try:
        file_name = "{:04d}".format(num_meshes)
        raycast_array = get_raycasts_from_metadata(f"meshes/{file_name}/framemetadata.json")
    except FileNotFoundError:
        print(f"No metadata file in frame {num_meshes}. Trying previous frame.")
        try:
            file_name = "{:04d}".format(num_meshes-1)
            raycast_array = get_raycasts_from_metadata(f"meshes/{file_name}/framemetadata.json")
        except FileNotFoundError:
            print(f"No metadata file in frame {num_meshes-1}. Terminating...")
    except:
        print("Error: something went wrong with the raycasts.")


    print("Raycasts received...")
    return raycast_array

def get_meshes_from_firebase(iphone, trial_name):
    """
    Find the names of all the paths which include the mesh files requested.

    :param iphone: (str) name of the iPhone where data is stored
    :param trial_name: (str) trial where you want meshes from
    :returns:
    """
    # removes the meshes directory, if it already exists
    os.system('rm -r meshes')
    # replaces it with a new meshes directory, which will contain the data
    # from this particular trial (iphone/trial_name)
    os.system('mkdir meshes')
    os.system(f'gsutil -m rsync -r gs://clew-sandbox.appspot.com/{IPHONE_UUIDS[iphone]}/{trial_name}/ meshes')
    # Count how many files there are in the directory, read protobufs in
    # reverse order
    num_meshes = len(os.listdir('meshes'))
    mesh_dict = []
    for i in range(num_meshes-1, 0, -1):
        try:
            file_name = "{:04d}".format(i)
            mat = read_protobuf(f"meshes/{file_name}/meshes.pb")
            mesh_dict += parse_meshes(mat)
        except FileNotFoundError:
            print(f"No mesh file in frame {i}. Continuing...")
        except:
            print("Error: something went wrong with the meshes.")


    print("Meshes received...")
    return mesh_dict

def get_vertices(mat, index):
    """
    Extracts vertices from data from a protobuf file.

    Args:
        mat: a dictionary of mesh data from a protobuf file
        index: an integer representing the index of the protobuf file
    Returns:
        A list of lists containing the x,y,z points of all vertices
    """
    # since transform is a 4x4, add a 1.0 at the end of the list
    return list(map(lambda x: np.array([x.x, x.y, x.z, 1.0]), mat.meshes[index].vertices))

def get_transform(mat, index):
    """
    Extracts transform matrix from mesh data from a protobuf file.
    Args:
        mat: a dictionary of mesh data from a protobuf file
        index: an integer representing the index of the protobuf file
    Returns:
        A list of lists containing the columns of the transform matrix
    """
    mesh_transform = mat.meshes[index].transform
    # Formatting the transform matrix that can be read
    real_transform = [
        [mesh_transform.c1.x, mesh_transform.c1.y, mesh_transform.c1.z,
            mesh_transform.c1.w],
        [mesh_transform.c2.x, mesh_transform.c2.y, mesh_transform.c2.z,
            mesh_transform.c2.w],
        [mesh_transform.c3.x, mesh_transform.c3.y, mesh_transform.c3.z,
            mesh_transform.c3.w],
        [mesh_transform.c4.x, mesh_transform.c4.y, mesh_transform.c4.z,
            mesh_transform.c4.w]
    ]
    return real_transform

def parse_meshes(mat):
    """
    Update dictionary so that values are Python objects instead of strings.
    :param mat: (dict?) raw Protobuf data read directly from the .pb file
    :returns: (list of dicts) containing parsed version of input data
    """
    data_dicts = []
    id_list = []
    for mesh_index in range(len(mat.meshes)):
        # Create a dict which has vertices and transform of mesh defined
        face = {}
        #check if mesh ID already has been crossed, otherwise add it to a list
        if mat.meshes[mesh_index].id not in id_list:
            id_list.append(mat.meshes[mesh_index].id)
            #parse transform
            face["transform"] = get_transform(mat, mesh_index)
            #parse geometry array
            face["vertices"] = get_vertices(mat, mesh_index)
            # Append this dict to data_dicts
            data_dicts.append(face)
    return data_dicts


def loc2glob(meshes):
    """
    Given info about planes in local coordinate system, convert to global coordinate system
    :param meshes: (list of dicts) contains parsed version of input data
    :returns: list of global vertices
    """
    res = []
    # Go through all the meshes in list
    for mesh in meshes:
        transform = np.array(mesh["transform"])
        vertices = np.array(mesh["vertices"])
        #check if vertices mesh is empty, skips if True
        if vertices.size == 0:
            continue
        #calculate vertices in the global coordinate system and store in dict
        global_array = vertices @ transform
        #convert from np.ndarray back to list
        res += global_array.tolist()

    print("Meshes were localized...")
    return res

def write_to_ply(meshes, ply_file_name):
    """
    Takes data from list of transformed vertices and writes them into ply file
    :param meshes: (list of dicts) containing parsed mesh data from Firebase
    :param ply_file_name: (str) desired name for the ply file
    """
    # Multiply unit vector vals by length
    with open(f"mesh_plys/{ply_file_name}.ply", "w") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(meshes)}\nproperty double x\nproperty double y\nproperty double z\nend_header\n")
        for verts in meshes:
            f.write(f'{verts[0]} {verts[1]} {verts[2]}\n')
    print("PLY file written...")

def write_to_raycast_ply(raycasts):
    """
    Takes data from raycasts and writes it to a ply file
    :param raycasts: (array of floats) raycast data extracted from metadata JSON
    """
    # Multiply unit vector vals by length
    with open(f"mesh_plys/final_raycast.ply", "w") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(raycasts)}\nproperty double x\nproperty double y\nproperty double z\nend_header\n")
        for ray in raycasts:
            f.write(f'{ray[0]} {ray[1]} {ray[2]}\n')
    print("Raycasts PLY file written...")


# def make_3d_file(meshes, prefix, file_tag):
#     """
#     Build CSV files of meshes that is compatible with Plotly 3dMesh. Creates one CSV file per possible
#     mesh classifciation
#     :param meshes: (list of dicts) containing parsed mesh data from Firebase
#     :param prefix: (str) prefix used for saving the CSVs
#     :returns: None, saves the CSVs locally
#     """
#
#     #build csvs
#     csv = '"x","y","z"\n'
#     for verts in meshes:
#         for vert in verts:
#             #x,y,z = (x,y,z) coordinates of a single vertex in a mesh
#             csv += f'"{verts[0]}","{verts[1]}","{verts[2]}"\n'  #the header of the CSVs
#
#     Path(f"3d_files/{prefix}").mkdir(exist_ok=True)
#     save_path = f"3d_files/{prefix}/{file_tag}-ply.csv"
#     print("saving csv at: ", save_path)
#     with open(save_path, "w") as f:
#         f.write(csv)
#         print("saving csv at: ", save_path)


def main(file_prefix, iphone, trial_name):
    """
    Pulls latest mesh data from Firebase, parses and stores as a pickle file.
    :param file_prefix: (str) desired prefix for the saved file
    :param iphone: (str) name of the iPhone where data is stored
    :param trial_name: (str) name of the trial where you want to pull meshes from
    :returns: (dict) parsed mesh data
    """
    # retrieve data from Firebase
    meshes = get_meshes_from_firebase(iphone, trial_name)
    raycasts = get_raycasts_from_firebase(iphone, trial_name)
    # localize meshes in global coordinate system
    loc_meshes = loc2glob(meshes)
    # create a ply file of the meshes
    write_to_ply(loc_meshes, file_prefix)
    write_to_raycast_ply(raycasts)
    print("Execution successful!")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
