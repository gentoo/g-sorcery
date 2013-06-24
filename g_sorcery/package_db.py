#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    package_db.py
    ~~~~~~~~~~~~~
    
    package database
    
    :copyright: (c) 2013 by Jauhien Piatlicki
    :license: GPL-2, see LICENSE for more details.
"""

import collections, glob, hashlib, json, os, shutil, tarfile, tempfile

Package = collections.namedtuple("Package", "category name version")

class FileJSON:
    def __init__(self, directory, name, mandatories):
        """
        Initialize

        mandatories -- list of mandatory keys
        """
        self.directory = os.path.abspath(directory)
        self.name = name
        self.path = os.path.join(directory, name)
        self.mandatories = mandatories

    def read(self):
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        content = {}
        if not os.path.isfile(self.path):
            for key in self.mandatories:
                content[key] = ""
            with open(self.path, 'w') as f:
                json.dump(content, f, indent=2, sort_keys=True)
        else:
            with open(self.path, 'r') as f:
                content = json.load(f)
            for key in self.mandatories:
                if not key in content:
                    raise KeyError
        return content

    def write(self, content):
        for key in self.mandatories:
            if not key in content:
                raise KeyError
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        with open(self.path, 'w') as f:
            json.dump(content, f, indent=2, sort_keys=True)


def hash_file(name, hasher, blocksize=65536):
    with open(name, 'rb') as f:
        buf = f.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(blocksize)
    return hasher.hexdigest()

def copy_all(src, dst):
    for f_name in os.listdir(src):
        src_name = os.path.join(src, f_name)
        dst_name = os.path.join(dst, f_name)
        if os.path.isdir(src_name):
            shutil.copytree(src_name, dst_name)
        else:
            shutil.copy2(src_name, dst_name)

class PackageDB:
    def __init__(self, directory, repo_uri="", db_uri=""):
        self.URI_NAME = 'uri.json'
        self.INFO_NAME = 'info.json'
        self.CATEGORIES_NAME = 'categories.json'
        self.PACKAGES_NAME = 'packages.json'
        self.VERSIONS_NAME = 'versions.json'
        self.directory = os.path.abspath(directory)
        self.reset_uri(repo_uri, db_uri)
        self.reset_db()

    def reset_uri(self, repo_uri="", db_uri=""):
        uri_f = FileJSON(self.directory, self.URI_NAME, ['repo_uri', 'db_uri'])
        uri = uri_f.read()
        if not repo_uri:
            self.repo_uri = uri['repo_uri']
        else:
            self.repo_uri = repo_uri
        if not db_uri:
            self.db_uri = uri['db_uri']
        else:
            self.db_uri = db_uri
        uri['repo_uri'] = self.repo_uri
        uri['db_uri'] = self.db_uri
        uri_f.write(uri)

    def reset_db(self):
        self.db = {}
        self.db['info'] = {}
        self.db['categories'] = {}
        self.db['packages'] = {}

    def generate(self, repo_uri=""):
        """
        Generates a new package database

        repo_uri -- repository uri
        """
        if repo_uri:
            self.repo_uri = repo_uri
        self.clean()
        self.generate_tree()
        self.write()
        self.manifest()

    def generate_tree(self):
        """
        Generate tree

        Should be implemented in a subclass
        """
        pass

    def sync(self, db_uri=""):
        if db_uri:
            self.db_uri = db_uri
        self.clean()
        real_db_uri = self.get_real_db_uri()
        download_dir = tempfile.TemporaryDirectory()
        if os.system('wget -P ' + download_dir.name + ' ' + real_db_uri):
            raise Exception('sync failed: ' + real_db_uri)
        
        temp_dir = tempfile.TemporaryDirectory()
        for f_name in glob.iglob(os.path.join(download_dir.name, '*.tar.gz')):
            with tarfile.open(f_name) as f:
                f.extractall(temp_dir.name)

        tempdb_dir = tempfile.TemporaryDirectory()
        tempdb = PackageDB(tempdb_dir.name)

        for d_name in os.listdir(temp_dir.name):
            current_dir = os.path.join(temp_dir.name, d_name)
            if not os.path.isdir(current_dir):
                continue
            copy_all(current_dir, tempdb_dir.name)

        if not tempdb.check_manifest():
            raise Exception('Manifest check failed.')

        self.clean()
        copy_all(tempdb_dir.name, self.directory)
        
        if not self.check_manifest():
            raise Exception('Manifest check failed, db inconsistent.')
                
        del download_dir
        del temp_dir
        del tempdb_dir
        
        self.read()

    def get_real_db_uri():
        return self.db_uri
            
    def manifest(self):
        categories = FileJSON(self.directory, self.CATEGORIES_NAME, [])
        categories = categories.read()
        manifest = {}
        names = [self.INFO_NAME, self.CATEGORIES_NAME, self.URI_NAME]
        for name in names:
            manifest[name] = hash_file(os.path.join(self.directory, name),
                                      hashlib.md5())
        for category in categories:
            category_path = os.path.join(self.directory, category)
            if not os.path.isdir(category_path):
                raise Exception('Empty category: ' + category)
            for root, dirs, files in os.walk(category_path):
                for f in files:
                    manifest[os.path.join(root[len(self.directory)+1:], f)] = \
                    hash_file(os.path.join(root, f), hashlib.md5())
        m = FileJSON(self.directory, 'manifest.json', [])
        m.write(manifest)

    def check_manifest(self):
        m = FileJSON(self.directory, 'manifest.json', [])
        manifest = m.read()
        
        result = True
        errors = []
        
        names = [self.INFO_NAME, self.CATEGORIES_NAME, self.URI_NAME]
        for name in names:
            if not name in manifest:
                raise Exception('Bad manifest: no ' + name + ' entry')

        for name, value in manifest.items():
            if hash_file(os.path.join(self.directory, name), hashlib.md5()) != \
                value:
                result = False
                errors.append(name)

        return (result, errors)

    def clean(self):
        shutil.rmtree(self.directory)
        self.reset_uri(self.repo_uri, self.db_uri)
        self.reset_db()

    def write(self):
        info_f = FileJSON(self.directory, self.INFO_NAME, [])
        categories_f = FileJSON(self.directory, self.CATEGORIES_NAME, [])
        info_f.write(self.db['info'])
        categories_f.write(self.db['categories'])
        for category in self.db['categories']:
            if not category in self.db['packages']:
                raise Exception('Empty category: ' + category)
            for package, versions in self.db['packages'][category].items():
                for version, content in versions.items():
                    f = FileJSON(os.path.join(self.directory, category, package),
                                 version + '.json', [])
                    f.write(content)
                    self.additional_write_version(category, package, version)
                f = FileJSON(os.path.join(self.directory, category, package),
                                     self.VERSIONS_NAME, [])
                f.write(list(versions))
                self.additional_write_package(category, package)
            f = FileJSON(os.path.join(self.directory, category),
                                     self.PACKAGES_NAME, [])
            f.write(list(self.db['packages'][category]))
            self.additional_write_category(category)
        self.additional_write()

    def additional_write_version(self, category, package, version):
        pass

    def additional_write_package(self, category, package):
        pass

    def additional_write_category(self, category):
        pass

    def additional_write(self):
        pass

    def read(self):
        sane, errors = self.check_manifest()
        if not sane:
            raise Exception('Manifest error: ' + str(errors))
        info_f = FileJSON(self.directory, self.INFO_NAME, [])
        categories_f = FileJSON(self.directory, self.CATEGORIES_NAME, [])
        self.db['info'] = info_f.read()
        self.db['categories'] = categories_f.read()
        for category in self.db['categories']:
            category_path = os.path.join(self.directory, category)
            if not os.path.isdir(category_path):
                raise Exception('Empty category: ' + category)
            
            f = FileJSON(category_path, self.PACKAGES_NAME, [])
            packages = f.read()
            if not packages:
                raise Exception('Empty category: ' + category)
            
            self.db['packages'][category] = {}
            for name in packages:
                package_path = os.path.join(category_path, name)
                if not os.path.isdir(category_path):
                    raise Exception('Empty package: ' + category + '/' + name)
                
                f = FileJSON(package_path, self.VERSIONS_NAME, [])
                versions = f.read()
                if not versions:
                    raise Exception('Empty package: ' + category + '/' + name)
                
                self.db['packages'][category][name] = {}
                for version in versions:
                    f = FileJSON(package_path, version + '.json', [])
                    description = f.read()
                    self.db['packages'][category][name][version] = description
                    self.additional_read_version(category, name, version)
                self.additional_read_package(category, name)
            self.additional_read_category(category)
        self.additional_read()

    def additional_read_version(self, category, package, version):
        pass

    def additional_read_package(self, category, package):
        pass

    def additional_read_category(self, category):
        pass

    def additional_read(self):
        pass
        
    def add_category(self, category, description={}):
        self.db['categories'][category] = description;
        self.db['packages'][category] = {}

    def add_package(self, package, description={}):
        category = package.category
        name = package.name
        version = package.version
        if not category in self.db['packages']:
            raise Exception('Non-existent category: ' + category)
        if not name in self.db['packages'][category]:
            self.db['packages'][category][name] = {}
        self.db['packages'][category][name][version] = description

    def list_categories(self):
        return list(self.db['categories'])

    def list_package_names(self, category):
        if not category in self.db['packages']:
            raise Exception('No such category: ' + category)
        return list(self.db['packages'][category])

    def list_package_versions(self, category, name):
        if not category in self.db['packages']:
            raise Exception('No such category: ' + category)
        if not name in self.db['packages'][category]:
            raise Exception('No such package: ' + name)
        return list(self.db['packages'][category][name])

    def list_all_packages(self):
        result = []
        for category in self.db['packages']:
            for name in self.db['packages'][category]:
                for version in self.db['packages'][category][name]:
                    result.append(Package(category, name, version))
        return result

    def get_package_description(self, package):
        #a possible exception should be catched in the caller
        return self.db['packages'][package.category][package.name][package.version]