from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MyMaterialCategory(models.Model):
    _name = 'my.material.category'
    _description = 'Material Category'
    _rec_name = 'name'

    name = fields.Char(string='Category Name', required=True)
    jigexian = fields.Char(string='Jix Exian')
    description = fields.Text(string='Descrip')

    @api.constrains('name')
    def _check_name_insensitive(self):
        for category in self:
            if not category.name:
                continue
            # Check if any other record exists with the same name (case-insensitive)
            domain = [('name', '=ilike', category.name), ('id', '!=', category.id)]
            if self.search_count(domain) > 0:
                raise ValidationError(f"Category '{category.name}' already exists! (Case-insensitive)")



    def _auto_init(self):
        # Pre-cleanup duplicates before adding unique constraint
        cr = self.env.cr
        
        # Check if table exists before querying
        cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'my_material_category'")
        if cr.fetchone():
            # 1. Normalize names to find duplicates (case-insensitive, strip whitespace)
            cr.execute("SELECT id, name FROM my_material_category")
            all_cats = cr.fetchall()
            
            normalized_map = {} # { 'normalized_name': [id1, id2, ...] }
            
            for cat_id, name in all_cats:
                if not name:
                    continue
                norm_name = name.strip().lower()
                if norm_name not in normalized_map:
                    normalized_map[norm_name] = []
                normalized_map[norm_name].append(cat_id)
                
            # 2. Process duplicates
            for norm_name, ids in normalized_map.items():
                if len(ids) > 1:
                    ids.sort() # Keep the lowest ID (oldest)
                    keep_id = ids[0]
                    delete_ids = tuple(ids[1:])
                    
                    # Check if my_material table exists before updating
                    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'my_material'")
                    if cr.fetchone():
                        # Update materials to use the kept category
                        cr.execute("""
                            UPDATE my_material 
                            SET category_id = %s 
                            WHERE category_id IN %s
                        """, (keep_id, delete_ids))
                    
                    # Delete the duplicates
                    cr.execute("DELETE FROM my_material_category WHERE id IN %s", (delete_ids,))
                    
        super(MyMaterialCategory, self)._auto_init()
