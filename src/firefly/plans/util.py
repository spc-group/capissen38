import numpy as np

__all__ = ["time_converter"]


def time_converter(total_seconds):
    """
    Convert time (in seconds) to a tuple of hours, minutes, seconds

    Parameters
    ==========
    total_seconds (float/int)

    Returns
    ==========
    tuple: hours, minutes, seconds
    """

    # use np.round instead round to prevent errors in round(float("nan"))
    hours = np.round(total_seconds // 3600)
    minutes = np.round((total_seconds % 3600) // 60)
    seconds = np.round(total_seconds % 60)
    return hours, minutes, seconds


def is_valid_value(value):
    """
    Check if the value is considered valid for inclusion in metadata.
    Valid values are non-None, and if they are str/list/tuple/dict, they should have a positive length.

    Parameters
    ==========
        value (any): The value to check.

    Returns
    ==========
        bool: True if the value is valid, False otherwise.
    """
    # Check if the value is None
    if value is None:
        return False
    # Check if the value is a collection with length
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) > 0
    # All other non-None values are considered valid
    return True


# -----------------------------------------------------------------------------
# :author:    Juanjuan Huang
# :email:     juanjuan.huang@anl.gov
# :copyright: Copyright © 2024, UChicago Argonne, LLC
#
# Distributed under the terms of the 3-Clause BSD License
#
# The full license is in the file LICENSE, distributed with this software.
#
# DISCLAIMER
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# -----------------------------------------------------------------------------
