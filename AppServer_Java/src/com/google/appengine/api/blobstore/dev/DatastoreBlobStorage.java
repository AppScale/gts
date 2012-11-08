package com.google.appengine.api.blobstore.dev;


import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.logging.Logger;

import com.google.appengine.api.NamespaceManager;
import com.google.appengine.api.blobstore.BlobInfo;
import com.google.appengine.api.blobstore.BlobKey;
import com.google.appengine.api.blobstore.BlobstoreInputStream;
import com.google.appengine.api.blobstore.BlobstoreService;
import com.google.appengine.api.datastore.Blob;
import com.google.appengine.api.datastore.DatastoreService;
import com.google.appengine.api.datastore.DatastoreServiceFactory;
import com.google.appengine.api.datastore.Entity;
import com.google.appengine.api.datastore.Key;
import com.google.appengine.api.datastore.KeyFactory;


public class DatastoreBlobStorage implements BlobStorage
{
	private static final Logger	logger				= Logger.getLogger(DatastoreBlobStorage.class.getName());
	private BlobInfoStorage		blobInfoStorage;
	private final String		_BLOB_CHUNK_KIND_	= "__BlobChunk__";
	DatastoreService			dataStoreService	= DatastoreServiceFactory.getDatastoreService();

	public DatastoreBlobStorage( BlobInfoStorage blobinfostorage )
	{
		this.blobInfoStorage = blobinfostorage;
	}

	public void deleteBlob( BlobKey blob_key ) throws IOException
	{
		logger.fine("deleteBlob called with key [" + blob_key.getKeyString() + "]");
		BlobInfo blobInfo = this.blobInfoStorage.loadBlobInfo(blob_key);

		long count = blobInfo.getSize() / BlobstoreService.MAX_BLOB_FETCH_SIZE;
		while (count >= 0)
		{
			// delete the content of the blob
			dataStoreService.delete(getLocalChunkKey(blob_key, count));
			count--;
		}
		// delete blob-meta key
		this.blobInfoStorage.deleteBlobInfo(blob_key);
	}

	private Key getLocalChunkKey( BlobKey blobKey, long count )
	{
		String namespace = NamespaceManager.get();
		Key localKey = null;
		try
		{
			NamespaceManager.set("");
			localKey = KeyFactory.createKey(_BLOB_CHUNK_KIND_, blobKey.getKeyString() + "__" + count);
			return localKey;
		}
		finally
		{
			NamespaceManager.set(namespace);
		}
	}

	@Override
	public InputStream fetchBlob( BlobKey arg0 ) throws IOException
	{
		return new BlobstoreInputStream(arg0);
	}

	@Override
	public boolean hasBlob( BlobKey arg0 )
	{
		return this.blobInfoStorage.loadBlobInfo(arg0) != null;
	}

	@Override
	public OutputStream storeBlob( final BlobKey blockKey ) throws IOException
	{
		logger.fine("storeBlob called with key [" + blockKey.getKeyString() + "]");
		return new ByteArrayOutputStream()
		{
			@Override
			public void close() throws IOException
			{
				super.close();
				byte[] stream = toByteArray();
				int blockCount = 0;
				int startPos = 0;
				int streamSize = stream.length;

				while (true)
				{
					int endPos = startPos + BlobstoreService.MAX_BLOB_FETCH_SIZE > streamSize ? streamSize : startPos + BlobstoreService.MAX_BLOB_FETCH_SIZE;

					byte[] block = Arrays.copyOfRange(stream, startPos, endPos);

					Entity blockEntity = new Entity(getLocalChunkKey(blockKey, blockCount));
					blockEntity.setProperty("block", new Blob(block));
					dataStoreService.put(blockEntity);
					blockCount++;
					if (endPos < streamSize)
					{
						startPos = endPos;
					}
					else
					{
						break;
					}
				}
			}
		};
	}

}
