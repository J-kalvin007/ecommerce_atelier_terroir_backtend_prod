

from .models import (
    Product,
    ProductImage,
)


class ProductService:

    @staticmethod
    def create_product(
        validated_data,
        images_data=None,
    ):

        product = Product.objects.create(
            **validated_data
        )

        if images_data:
            images_to_create = [
                ProductImage(product=product, **image_data)
                for image_data in images_data
            ]
            ProductImage.objects.bulk_create(images_to_create)

        return product

    @staticmethod
    def update_product(
        product,
        validated_data,
    ):

        for attr, value in validated_data.items():
            setattr(
                product,
                attr,
                value
            )

        product.save()

        return product

    @staticmethod
    def delete_product(
        product,
    ):
        product.delete()