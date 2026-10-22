"""Read-only validation of a relocated legacy package without rewriting references."""
import argparse
from contextlib import contextmanager
from pathlib import Path

import actions
import authority
import capture
import impact
import operating
import publication
import reconcile
import registers
import scope
import workflow


@contextmanager
def relocated_paths(root, original_root):
    """Use logical recorded paths for comparisons, mapped physical paths for reads.

    Scoped to these single-threaded validation modules, never pathlib globally.
    Every mapped read is constrained to the selected checkout, even when the old
    workspace still exists. No fallback, symlink escape or write is permitted.
    """
    physical_root = root.resolve(strict=True)
    logical_root = original_root
    if not logical_root.is_absolute() or '..' in logical_root.parts:
        raise ValueError('Original root must be an absolute normalized directory')
    base = type(Path())
    modules = (actions, authority, capture, impact, operating, publication,
               reconcile, registers, scope, workflow)
    # Tests/operators may import a validator from a parent checkout and validate a
    # relocated copy. Resolve module-relative defaults against the selected copy,
    # including when the export originally lived beneath the recorded root.
    code_files = {str(Path(module.__file__)): Path('regulatory-change-impact-brief/scripts') / Path(module.__file__).name
                  for module in modules}

    class ReviewPath(base):
        def physical(self):
            plain = Path(str(self))
            if str(plain) in code_files:
                relative = code_files[str(plain)]
            elif plain.is_absolute():
                try:
                    relative = plain.relative_to(logical_root)
                except ValueError:
                    # Imported modules' __file__ points into the relocated checkout.
                    try:
                        relative = plain.relative_to(physical_root)
                    except ValueError:
                        raise ValueError('Absolute reference outside declared roots: ' + str(plain)) from None
            else:
                relative = plain
            target = (physical_root / relative).resolve()
            if not target.is_relative_to(physical_root):
                raise ValueError('Reference escapes selected checkout: ' + str(self))
            return target

        def open(self, mode='r', *args, **kwargs):
            if mode not in {'r', 'rb', 'rt'}:
                raise ValueError('Portable validation is read-only')
            return self.physical().open(mode, *args, **kwargs)

        def stat(self, *args, **kwargs):
            return self.physical().stat(*args, **kwargs)

        def resolve(self, strict=False):
            physical = self.physical().resolve(strict=strict)
            return ReviewPath(logical_root / physical.relative_to(physical_root))

    originals = {module: module.Path for module in modules if hasattr(module, 'Path')}
    try:
        for module in originals:
            module.Path = ReviewPath
        yield ReviewPath
    finally:
        for module, value in originals.items():
            module.Path = value


def verify(root, original_root, package='deliverables'):
    root = Path(root).resolve(strict=True)
    original_root = Path(original_root)
    package = Path(package)
    if package.is_absolute() or '..' in package.parts:
        raise ValueError('Package must be repository-relative')
    with workflow.workspace(root), relocated_paths(root, original_root) as logical:
        result = workflow.verify_run(logical(original_root / package), logical(original_root))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=scope.ROOT)
    parser.add_argument('--original-root', type=Path, required=True,
                        help='Explicit recorded repository prefix; never accessed directly')
    parser.add_argument('--package', default='deliverables')
    args = parser.parse_args()
    result = verify(args.root, args.original_root, args.package)
    print('Relocated seven-stage package verified without rewriting bytes; run ' +
          result['run_id'] + '; publication ' + result['state']['publication_status'])


if __name__ == '__main__':
    main()
