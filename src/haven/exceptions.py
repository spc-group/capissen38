from ophydregistry.exceptions import (  # noqa: F401
    ComponentNotFound,
    InvalidComponentLabel,
    MultipleComponentsFound,
)


class NoEnergies(ValueError):
    """The plan parameters do not result in any energies being selected for scanning."""

    ...


class GainOverflow(RuntimeError):
    """The gain is trying to be set to a value that is not allowed."""

    ...


# class ComponentNotFound(IndexError):
#     """Registry looked for a component, but it wasn't registered."""

#     ...


# class MultipleComponentsFound(IndexError):
#     """Registry looked for a single component, but found more than one."""

#     ...


# class InvalidComponentLabel(TypeError):
#     """Registry looked for a component, but the label provided is not vlaid."""

#     ...


class FileNotWritable(IOError):
    """Output file is available but does not have write intent."""

    ...


class XDIFilenameKeyNotFound(KeyError):
    """The format string for an XDI filename has unknown placeholders."""

    ...


class InvalidPV(ValueError):
    """A process variable path or similar is expected, but the path
    provided is not valid.

    """

    ...


class DocumentNotFound(RuntimeError):
    """An attempt was made to use a document, but the requested document
    was not available.

    """

    ...


class IOCTimeout(RuntimeError):
    """The IOC did not start within the allotted time."""

    ...


class UnknownDeviceConfiguration(ValueError):
    """The configuration for a device does not match the known options."""

    ...


class InvalidHarmonic(ValueError):
    """The requested harmonic is invalid for this insertion device."""

    ...


class SignalNotFound(KeyError):
    """The dataset is not present in the run."""

    ...


class EmptySignalName(ValueError): ...


class InvalidTransformation(TypeError):
    """The data cannot be transformed to a new y-data signal."""

    ...


class InvalidScanParameters(ValueError):
    """The given scan parameters will not produce a sane scan."""

    ...


class PluginNotPrimed(RuntimeError):
    """The detector plugin has not yet received a dataframe.

    Prior to starting capture for some detector file writer plugins,
    the plugin need to receive at least one dataframe in order to
    extract the dimensions, type, etc. of the data it will receive.

    """

    ...


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2023, UChicago Argonne, LLC
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
