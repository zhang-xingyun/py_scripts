from __future__ import absolute_import
import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from dp_tool_base.data import ImageDataLoader, ImageDataWriter


logger = logging.getLogger(__name__)


class MergePrediction:
    """Simplely Merge prediction results of json files.

    Parameters
    ----------
    source_classnames : List
        Names of all input classes

    """

    def __init__(
        self,
        source_classnames: List,
    ):
        super(MergePrediction, self).__init__()
        self._source_classnames = source_classnames

    def _merge_data_with_others(self, other_image_datas):
        current_image_data = other_image_datas[0]
        for class_name in self._source_classnames:
            for other_image_data in other_image_datas[1:]:
                if class_name not in other_image_data:
                    continue
                if class_name not in current_image_data:
                    current_image_data[class_name] = other_image_data[
                        class_name
                    ]
                else:
                    current_image_data[class_name] += other_image_data[
                        class_name
                    ]

        current_image_data["selections"] = {}
        for class_name in self._source_classnames:
            current_image_data["selections"][class_name] = current_image_data[
                class_name
            ]  # noqa
        return current_image_data

    def __call__(
        self, loaders: List["ImageDataLoader"], writer: "ImageDataWriter"
    ):
        processed_files_amount = 0
        for datas in zip(*loaders):
            image_uuid = datas[0].image_uuid
            for other_data in datas[1:]:
                assert image_uuid == other_data.image_uuid
            processed_files_amount += 1
            if processed_files_amount % 100 == 0:
                logger.info(f"Processed {processed_files_amount}th file")
            merge_results = self._merge_data_with_others(datas)
            write_infos = [merge_results]
            writer.write(write_infos)
