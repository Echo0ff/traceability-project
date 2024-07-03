from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision = "3f2dfea2f8a4"
down_revision = "879123891b22"
branch_labels = None
depends_on = None


def upgrade():
    # 添加新列
    op.add_column(
        "grower", sa.Column("business_license_photos", sa.JSON(), nullable=True)
    )

    # 修改 crop_yield 列
    op.alter_column(
        "grower",
        "crop_yield",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
    )

    # 修改 id_card_photo 列
    op.execute(
        """
    ALTER TABLE grower 
    ALTER COLUMN id_card_photo TYPE JSON 
    USING CASE 
        WHEN id_card_photo IS NULL THEN NULL 
        WHEN id_card_photo = '' THEN '[]'::json
        ELSE json_build_array(id_card_photo) 
    END
    """
    )

    # 修改 land_ownership_certificate 列
    op.execute(
        """
    ALTER TABLE grower 
    ALTER COLUMN land_ownership_certificate TYPE JSON 
    USING CASE 
        WHEN land_ownership_certificate IS NULL THEN NULL 
        WHEN land_ownership_certificate = '' THEN '[]'::json
        ELSE json_build_array(land_ownership_certificate) 
    END
    """
    )

    # 将 business_license_photo 数据迁移到 business_license_photos
    op.execute(
        """
    UPDATE grower 
    SET business_license_photos = 
        CASE 
            WHEN business_license_photo IS NULL THEN NULL 
            WHEN business_license_photo = '' THEN '[]'::json
            ELSE json_build_array(business_license_photo) 
        END
    """
    )

    # 删除旧列
    op.drop_column("grower", "business_license_photo")


def downgrade():
    # 添加旧列
    op.add_column(
        "grower",
        sa.Column(
            "business_license_photo", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
    )

    # 将 JSON 数据转回字符串
    op.execute(
        """
    UPDATE grower 
    SET business_license_photo = 
        CASE 
            WHEN business_license_photos IS NULL THEN NULL 
            WHEN business_license_photos::text = '[]' THEN ''
            ELSE business_license_photos->0 
        END
    """
    )

    # 修改列类型回 VARCHAR
    op.alter_column(
        "grower",
        "land_ownership_certificate",
        existing_type=sa.JSON(),
        type_=sa.VARCHAR(),
        postgresql_using="land_ownership_certificate::text",
    )
    op.alter_column(
        "grower",
        "id_card_photo",
        existing_type=sa.JSON(),
        type_=sa.VARCHAR(),
        postgresql_using="id_card_photo::text",
    )

    # 修改 crop_yield 列回原类型
    op.alter_column(
        "grower",
        "crop_yield",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.DOUBLE_PRECISION(precision=53),
        existing_nullable=True,
    )

    # 删除新列
    op.drop_column("grower", "business_license_photos")
